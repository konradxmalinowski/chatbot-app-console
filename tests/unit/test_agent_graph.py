"""Unit tests for the human-in-the-loop AgentGraph mechanism.

Uses the deterministic FakeChatModel (see conftest). Every LLM call is mocked; no
network. Tool logs are redirected into tmp_path.
"""

import json

import pytest

from agent.graph import AgentGraph


@pytest.fixture
def graph(tmp_path, monkeypatch, fake_llm):
    # LOGS_DIR is used inside agent.graph._log_tool_attempt via the module global.
    import agent.graph as agent_graph

    monkeypatch.setattr(agent_graph, "LOGS_DIR", tmp_path / "logs")
    return AgentGraph(fake_llm), fake_llm, tmp_path / "logs"


def _read_log_entries(logs_dir):
    log_file = logs_dir / "agent.jsonl"
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text().splitlines() if line]


class TestApprove:
    def test_approve_executes_tool_and_clears_pending(self, graph):
        agent_graph, _llm, logs_dir = graph
        session_id = "approve-session"

        agent_graph.start_turn(session_id, "please calc this for me")
        assert agent_graph.has_pending_approval(session_id) is True

        agent_graph.resume_approved(session_id, "cli-user")

        assert agent_graph.has_pending_approval(session_id) is False
        assert agent_graph.get_final_response(session_id) != ""

        entries = _read_log_entries(logs_dir)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["tool"] == "calculator"
        assert entry["declined"] is False
        # The tool actually ran: 2 + 2 == 4.
        assert entry["result"] == "4"


class TestReject:
    def test_reject_never_executes_and_single_ack_call(self, graph):
        agent_graph, llm, logs_dir = graph
        session_id = "reject-session"

        agent_graph.start_turn(session_id, "please calc this for me")
        assert agent_graph.has_pending_approval(session_id) is True
        invokes_before_reject = llm.invoke_count

        agent_graph.resume_rejected(session_id, "cli-user")

        # Exactly one further LLM call to acknowledge the decline — no retry loop.
        assert llm.invoke_count == invokes_before_reject + 1
        assert agent_graph.has_pending_approval(session_id) is False
        assert agent_graph.get_final_response(session_id) != ""

        entries = _read_log_entries(logs_dir)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["tool"] == "calculator"
        assert entry["declined"] is True
        # The tool never ran, so no real result was recorded.
        assert entry["result"] is None


class TestMultiToolDisclosure:
    def test_all_pending_tool_calls_are_disclosed(self, graph):
        """Regression test for the HIGH-severity fix: when the model proposes
        several tool calls in one turn, get_pending_tool_calls must return EVERY
        one of them (informed consent), not just the first.
        """
        agent_graph, _llm, _logs_dir = graph
        session_id = "multi-session"

        agent_graph.start_turn(session_id, "please run a multitool batch")

        assert agent_graph.has_pending_approval(session_id) is True
        pending = agent_graph.get_pending_tool_calls(session_id)

        assert len(pending) == 2
        names = {call.name for call in pending}
        assert names == {"calculator", "read_doc"}

    def test_no_pending_calls_when_not_paused(self, graph):
        agent_graph, _llm, _logs_dir = graph
        session_id = "plain-session"

        agent_graph.start_turn(session_id, "just say hello please")

        assert agent_graph.has_pending_approval(session_id) is False
        assert agent_graph.get_pending_tool_calls(session_id) == []
        assert agent_graph.get_final_response(session_id) != ""
