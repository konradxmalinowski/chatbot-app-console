"""Tools available to the Phase 4 LangGraph agent.

Every tool here is defensive by design: none of them ever raise past their own
boundary. A tool failure (bad input, network error, path traversal attempt) is
caught and turned into a plain string result instead, so the graph can feed it back
to the LLM as a normal observation rather than crashing the whole turn. This mirrors
`rag/loader.py`'s "never fatal, just report and move on" philosophy.
"""

import ast
import logging
import math
import operator

from langchain_core.tools import tool

from constants import DOCS_DIR
from rag.loader import SUPPORTED_EXTENSIONS, _read_pdf, _read_text_file

logger = logging.getLogger(__name__)


@tool
def web_search(query: str) -> str:
    """Search the web for current information using DuckDuckGo and return a short
    summary of the top results. Use this when you need up-to-date information that
    is not in your training data or in the local documents.
    """
    if not query or not query.strip():
        return "Search unavailable: query must not be empty."

    try:
        # Imported lazily so the rest of the module (and the calculator/read_doc
        # tools) works even if duckduckgo-search is temporarily unavailable.
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query.strip(), max_results=5))
    except Exception as exc:  # noqa: BLE001 — DDGS raises assorted, undocumented
        # exception types (network errors, rate limiting, upstream HTML changes to
        # the unofficial API this package scrapes); any of them must degrade to a
        # plain observation string, never crash the graph turn.
        logger.warning("web_search failed for query %r: %s", query, exc)
        return f"Search unavailable: {exc}"

    if not results:
        return f"No search results found for: {query}"

    lines = []
    for i, result in enumerate(results, start=1):
        title = result.get("title", "").strip()
        body = result.get("body", "").strip()
        href = result.get("href", "").strip()
        lines.append(f"{i}. {title}\n   {body}\n   {href}")
    return "\n".join(lines)


# --- calculator: AST-based restricted evaluator, no eval()/exec() ---------------

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARYOPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Python ints are arbitrary-precision, so `ast.Pow` alone has no cost limit — an
# innocuous-looking expression like "9**9**9" (≈369 million digits) will pin a CPU
# core and grow unbounded memory for a long time before ever raising. Reject any
# exponentiation whose *result* would exceed this many bits, estimated cheaply via
# log2 before actually computing it, rather than computing first and hoping an
# exception cuts it short.
_MAX_POW_RESULT_BITS = 10_000


def _check_pow_cost(base: float, exponent: float) -> None:
    if base == 0 or exponent == 0:
        return
    estimated_bits = abs(exponent) * math.log2(abs(base) + 1e-9)
    if estimated_bits > _MAX_POW_RESULT_BITS:
        raise ValueError(
            f"result too large to compute (estimated {estimated_bits:.0f} bits, "
            f"limit {_MAX_POW_RESULT_BITS})"
        )


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate a restricted arithmetic AST node.

    Only numeric constants and +, -, *, /, **, unary +/- are permitted. Anything
    else (names, calls, attribute access, strings, comprehensions, ...) raises
    ValueError before it is ever evaluated — this is the entire security boundary
    that replaces eval()/exec() for this tool.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"unsupported constant: {node.value!r}")
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise ValueError(f"unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Pow:
            _check_pow_cost(left, right)
        return _ALLOWED_BINOPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise ValueError(f"unsupported unary operator: {op_type.__name__}")
        return _ALLOWED_UNARYOPS[op_type](_eval_node(node.operand))

    raise ValueError(f"unsupported expression element: {type(node).__name__}")


@tool
def calculator(expression: str) -> str:
    """Evaluate a pure arithmetic expression (numbers and + - * / ** ( ) only) and
    return the numeric result as a string. Does not support variables, function
    calls, or any non-arithmetic input.
    """
    if not expression or not expression.strip():
        return "Invalid expression: input must not be empty."

    try:
        parsed = ast.parse(expression, mode="eval")
        if not isinstance(parsed, ast.Expression):
            return "Invalid expression: only single expressions are supported."
        result = _eval_node(parsed.body)
    except ZeroDivisionError:
        return "Invalid expression: division by zero."
    except (ValueError, SyntaxError, TypeError) as exc:
        return f"Invalid expression: {exc}"
    except Exception as exc:  # noqa: BLE001 — never let a malformed expression
        # crash the graph turn; report it as an invalid-expression observation.
        logger.warning("calculator failed for expression %r: %s", expression, exc)
        return f"Invalid expression: {exc}"

    return str(result)


# --- read_doc: path-confined file reader -----------------------------------------


@tool
def read_doc(filename: str) -> str:
    """Read the text content of a document (.pdf, .txt, or .md) located in the
    local docs directory. Only accepts a bare filename (or a relative path) inside
    that directory — cannot read files outside it.
    """
    if not filename or not filename.strip():
        return "Access denied: filename must not be empty."

    try:
        docs_root = DOCS_DIR.resolve()
        candidate = (DOCS_DIR / filename).resolve()
    except (OSError, ValueError) as exc:
        # .resolve() can raise on malformed input (e.g. an embedded null byte)
        # before the containment check below ever runs. Not a traversal bypass —
        # it fails closed — but this module's own contract is "never raise past
        # this boundary," so it's handled the same way as every other rejection.
        logger.warning("read_doc rejected malformed filename %r: %s", filename, exc)
        return "Access denied: malformed filename."

    # Reject before ever opening the file: the resolved candidate must still be
    # inside docs_root. Catches "../../etc/passwd", absolute-path escapes (joining
    # an absolute path onto DOCS_DIR replaces it entirely in pathlib, so this check
    # is what actually catches that case), and symlink escapes.
    if not candidate.is_relative_to(docs_root):
        logger.warning("read_doc rejected path traversal attempt: %r", filename)
        return "Access denied: path is outside the allowed documents directory."

    if not candidate.exists() or not candidate.is_file():
        return f"Not found: {filename}"

    extension = candidate.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return f"Unsupported file type '{extension}' for {filename}."

    text = _read_pdf(candidate) if extension == ".pdf" else _read_text_file(candidate)
    if text is None:
        return f"Could not read {filename} (unreadable or corrupted file)."
    if not text.strip():
        return f"{filename} is empty."

    return text
