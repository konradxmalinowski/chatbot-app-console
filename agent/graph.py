"""LangGraph agent construction and the shared human-in-the-loop interface used by
both the CLI (``main.py --agent``) and the REST API (``api/main.py``'s
``/agent*`` routes) — mirrors how ``chain_builder.py``/``rag/bootstrap.py`` are
shared between those two entry points in Phases 2-3, so graph-construction logic
lives in exactly one place.

Human-in-the-loop mechanism
----------------------------
The graph is compiled with ``interrupt_before=["tools"]``: whenever the LLM node
proposes a tool call, execution pauses *before* the tools node runs, and the
checkpointer (`MemorySaver`, in-memory, matching this project's existing
in-memory/JSON-backed scope) persists the paused state under ``thread_id`` (the
validated ``session_id``, reused from Phase 2/3 — no new ID scheme).

- Approve: resume normally (``graph.invoke(None, config)``). LangGraph's prebuilt
  ``ToolNode`` executes the pending tool call(s) for real and the graph continues.
- Reject: inject a synthetic ``ToolMessage`` per pending tool call, marked as
  declined, via ``graph.update_state(..., as_node="tools")`` — this makes the
  checkpoint look as if the tools node ran and produced a "declined" observation
  instead of a real result, without ever invoking the tool. Then resume normally;
  the llm node sees the decline and must respond without retrying that tool call
  (enforced via the system prompt instruction in ``AGENT_SYSTEM_PROMPT_SUFFIX``).

Known, documented limitation: if the LLM proposes more than one tool call in a
single turn (parallel tool calling), the approval surfaces the first as the
representative pending tool, but approve/reject acts on the whole batch at once
(this is ``ToolNode``'s native batch semantics) — there is no partial approval of
one call within a batch. Nothing in the batch ever executes without going through
this same approve/reject gate, so the "no tool runs without approval" invariant
still holds; it is just coarser-grained than single-call approval in that rare case.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agent.tools import calculator, read_doc, web_search
from constants import (
    AGENT_LOG_FILE,
    AGENT_SYSTEM_PROMPT_SUFFIX,
    LOGS_DIR,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

TOOLS = [web_search, calculator, read_doc]

_AGENT_SYSTEM_MESSAGE = SYSTEM_PROMPT + AGENT_SYSTEM_PROMPT_SUFFIX


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@dataclass(frozen=True)
class PendingToolCall:
    """The tool call the graph is currently paused on, awaiting approval."""

    id: str
    name: str
    args: dict


# Cap on how much of a tool result gets written to logs/agent.jsonl. Tool results
# (e.g. read_doc returning a whole file's text) can be arbitrarily large; logging
# them in full would duplicate document contents in plaintext into an unrotated
# log outside DOCS_DIR's access boundary, and would let one read_doc/web_search
# call bloat the log file unboundedly. The full result still reaches the LLM (and
# the caller, via the eventual response) — only the *logged* copy is truncated.
_LOG_RESULT_MAX_CHARS = 500


def _truncate_for_log(result: str | None) -> str | None:
    if result is None or len(result) <= _LOG_RESULT_MAX_CHARS:
        return result
    return result[:_LOG_RESULT_MAX_CHARS] + f"...[truncated, {len(result)} chars total]"


def _log_tool_attempt(
    session_id: str,
    tool_name: str,
    args: dict,
    result: str | None,
    declined: bool,
    approved_by: Literal["cli-user", "api-client"],
) -> None:
    """Append one JSON line per tool-call attempt to logs/agent.jsonl.

    Never raises: a logging failure must not abort an otherwise-successful (or
    otherwise-rejected) tool call turn.
    """
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "tool": tool_name,
            "args": args,
            "result": _truncate_for_log(result),
            "declined": declined,
            "approved_by": approved_by,
        }
        log_path = LOGS_DIR / AGENT_LOG_FILE
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.error("Failed to write agent tool-call log entry: %s", exc)


class AgentGraph:
    """Wraps the compiled LangGraph StateGraph and exposes a small, entry-point
    agnostic interface for driving one user turn through to completion, pausing at
    tool-call approval boundaries as needed.
    """

    def __init__(self, llm) -> None:
        self._llm_with_tools = llm.bind_tools(TOOLS)
        self._checkpointer = MemorySaver()
        self._graph = self._build_graph()

    def _call_llm(self, state: AgentState) -> dict:
        messages = state["messages"]
        if not messages or messages[0].type != "system":
            messages = [("system", _AGENT_SYSTEM_MESSAGE), *messages]
        response = self._llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("llm", self._call_llm)
        builder.add_node("tools", ToolNode(TOOLS))
        builder.set_entry_point("llm")
        builder.add_conditional_edges(
            "llm", tools_condition, {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "llm")
        return builder.compile(
            checkpointer=self._checkpointer, interrupt_before=["tools"]
        )

    @staticmethod
    def _config(session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    def _last_ai_message(self, session_id: str) -> AIMessage | None:
        snapshot = self._graph.get_state(self._config(session_id))
        messages = snapshot.values.get("messages", []) if snapshot.values else []
        if not messages:
            return None
        last = messages[-1]
        return last if isinstance(last, AIMessage) else None

    def has_pending_approval(self, session_id: str) -> bool:
        """True if the graph is currently paused before executing a tool call for
        this session (i.e. an approve/reject call would be meaningful right now).
        """
        snapshot = self._graph.get_state(self._config(session_id))
        return bool(snapshot.next)

    def get_pending_tool_calls(self, session_id: str) -> list[PendingToolCall]:
        """Return every tool call the graph wants to run, or an empty list if the
        graph is not currently paused on one.

        Returns the *full* batch, not just the first: the LLM can propose several
        tool calls in one turn (parallel tool calling), and approving/rejecting is
        all-or-nothing for the whole batch (LangGraph's `ToolNode` semantics — see
        the module docstring). Showing only the first call to whoever is approving
        would mean they approve real, unseen side effects alongside the one they
        actually looked at — informed consent requires disclosing all of them, even
        though the approve/reject decision itself still applies to the batch as a
        unit, not per-call.
        """
        if not self.has_pending_approval(session_id):
            return []
        last = self._last_ai_message(session_id)
        if last is None or not last.tool_calls:
            return []
        return [
            PendingToolCall(id=call["id"], name=call["name"], args=call["args"])
            for call in last.tool_calls
        ]

    def get_final_response(self, session_id: str) -> str:
        """Return the most recent assistant text response for this session (call
        only once ``has_pending_approval`` is False).
        """
        snapshot = self._graph.get_state(self._config(session_id))
        messages = snapshot.values.get("messages", []) if snapshot.values else []
        for message in reversed(messages):
            if isinstance(message, AIMessage) and not message.tool_calls:
                return message.content
        return ""

    def start_turn(self, session_id: str, user_message: str) -> None:
        """Begin (or continue) a conversation turn with a new user message. Runs
        until the graph either finishes or pauses on a tool-call approval boundary.
        """
        config = self._config(session_id)
        self._graph.invoke(
            {"messages": [HumanMessage(content=user_message)]}, config=config
        )

    def resume_approved(
        self, session_id: str, approved_by: Literal["cli-user", "api-client"]
    ) -> None:
        """Resume execution, letting the pending tool call(s) actually run. Logs
        each executed call with its real result.
        """
        config = self._config(session_id)
        last = self._last_ai_message(session_id)
        pending_calls = list(last.tool_calls) if last is not None else []

        self._graph.invoke(None, config=config)

        snapshot = self._graph.get_state(config)
        messages = snapshot.values.get("messages", []) if snapshot.values else []
        results_by_id = {
            m.tool_call_id: m.content for m in messages if isinstance(m, ToolMessage)
        }
        for call in pending_calls:
            _log_tool_attempt(
                session_id=session_id,
                tool_name=call["name"],
                args=call["args"],
                result=results_by_id.get(call["id"]),
                declined=False,
                approved_by=approved_by,
            )

    def resume_rejected(
        self, session_id: str, approved_by: Literal["cli-user", "api-client"]
    ) -> None:
        """Resume execution without running the pending tool call(s): injects a
        declined-tool-call observation instead, then continues the graph so the
        LLM must acknowledge it rather than silently retrying.
        """
        config = self._config(session_id)
        last = self._last_ai_message(session_id)
        pending_calls = list(last.tool_calls) if last is not None else []

        decline_messages = []
        for call in pending_calls:
            _log_tool_attempt(
                session_id=session_id,
                tool_name=call["name"],
                args=call["args"],
                result=None,
                declined=True,
                approved_by=approved_by,
            )
            decline_messages.append(
                ToolMessage(
                    content=(
                        f"Tool call to '{call['name']}' was declined by the user. "
                        "Do not retry this exact tool call. Acknowledge that you "
                        "cannot complete this action, or propose an alternative "
                        "that does not require this tool."
                    ),
                    tool_call_id=call["id"],
                    name=call["name"],
                )
            )

        if decline_messages:
            self._graph.update_state(
                config, {"messages": decline_messages}, as_node="tools"
            )
        self._graph.invoke(None, config=config)
