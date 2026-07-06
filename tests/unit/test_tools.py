"""Unit tests for agent/tools.py safety boundaries.

The calculator must be a real (eval-free) arithmetic evaluator that rejects code
injection and cannot be turned into a CPU/memory bomb. read_doc must be confined to
DOCS_DIR and reject traversal / absolute-path escapes.
"""

import time

import pytest

from agent import tools

# calculator returns the raw tool result; the @tool decorator wraps the function,
# so we call the underlying implementation via .func for a plain string result.
calculator = tools.calculator.func
read_doc = tools.read_doc.func

# A generous ceiling: the cost guard should reject the bomb in well under this.
POW_BOMB_MAX_SECONDS = 2.0


class TestCalculatorHappyPath:
    def test_basic_arithmetic(self):
        assert calculator("2 + 3 * 4") == "14"

    def test_parentheses_and_power(self):
        assert calculator("(2 + 3) ** 2") == "25"

    def test_division_by_zero_is_reported_not_raised(self):
        assert "division by zero" in calculator("1 / 0").lower()


class TestCalculatorRejectsInjection:
    def test_rejects_dunder_import_injection(self):
        result = calculator("__import__('os').system('echo pwned')")
        assert result.lower().startswith("invalid expression")

    def test_rejects_name_reference(self):
        result = calculator("os")
        assert result.lower().startswith("invalid expression")

    def test_rejects_function_call(self):
        result = calculator("print(1)")
        assert result.lower().startswith("invalid expression")

    def test_rejects_attribute_access(self):
        result = calculator("(1).__class__")
        assert result.lower().startswith("invalid expression")


class TestCalculatorCostBomb:
    def test_pow_bomb_rejected_quickly(self):
        """9**9**9 would pin a CPU core for a long time if actually computed. The
        log2-bits cost guard must reject it fast instead of hanging.
        """
        start = time.monotonic()
        result = calculator("9**9**9")
        elapsed = time.monotonic() - start

        assert elapsed < POW_BOMB_MAX_SECONDS, (
            f"cost guard did not short-circuit: took {elapsed:.2f}s"
        )
        assert result.lower().startswith("invalid expression")
        assert "too large" in result.lower()


class TestReadDocConfinement:
    @pytest.fixture
    def docs_dir(self, tmp_path, monkeypatch):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "faq.md").write_text("Hello from the docs.", encoding="utf-8")
        # DOCS_DIR is imported into agent.tools' namespace, so patch it there.
        monkeypatch.setattr(tools, "DOCS_DIR", docs)
        return docs

    def test_reads_file_inside_docs_dir(self, docs_dir):
        assert read_doc("faq.md") == "Hello from the docs."

    def test_rejects_parent_traversal(self, docs_dir):
        # The secret lives one level above docs/, reachable only via traversal.
        (docs_dir.parent / "secret.txt").write_text("top secret", encoding="utf-8")
        result = read_doc("../secret.txt")
        assert "access denied" in result.lower()
        assert "top secret" not in result

    def test_rejects_absolute_path_escape(self, docs_dir):
        result = read_doc("/etc/passwd")
        assert "access denied" in result.lower()
        assert "root:" not in result

    def test_missing_file_reports_not_found(self, docs_dir):
        assert read_doc("does-not-exist.md").lower().startswith("not found")

    def test_unsupported_extension_rejected(self, docs_dir):
        (docs_dir / "data.csv").write_text("a,b,c", encoding="utf-8")
        assert "unsupported file type" in read_doc("data.csv").lower()
