"""LangGraph IT helpdesk: a hand-built supervisor that hands each request to one of two worker subgraphs.

- supervisor: a model with two handoff tools, transfer_to_diagnostics and transfer_to_actions. A handoff is a
  Command to the worker node, answered with a ToolMessage so the transcript stays valid for a real model.
- diagnostics worker (subgraph): model and ToolNode loop over check_device_status.
- actions worker (subgraph): model and ToolNode loop over reset_password, request_approval and grant_admin_access,
  with an approval gate: after request_approval the graph pauses with interrupt() for the approver, so an admin
  access request ends interrupted and grant_admin_access is never called without approval.

The graph is compiled with an InMemorySaver checkpointer, which interrupt() needs. The model is simulated by
SimulatedHelpdeskModel unless build_live_agent is used. build_ungated_agent is the same agent after a refactor that
wired the actions tool loop straight back to the model, which drops the gate.
"""

import json
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

from examples.helpdesk import rules
from examples.helpdesk.rules import (
    ACTIONS_PROMPT,
    DIAGNOSTICS_PROMPT,
    HANDOFF_TEAMS,
    NOT_APPROVED,
    SUPERVISOR_PROMPT,
    ToolRequest,
    ToolResult,
    next_step,
)

LIVE_MODEL_ID = "us.anthropic.claude-haiku-5-5"


@tool
def transfer_to_diagnostics() -> str:
    """Hand the request to the diagnostics team, which checks a device's health, connectivity and status."""
    return "Transferred to diagnostics."


@tool
def transfer_to_actions() -> str:
    """Hand the request to the actions team, which resets passwords and handles admin access requests."""
    return "Transferred to actions."


@tool
def check_device_status(device_id: str) -> str:
    """Return a device's status as JSON: online, last_seen, os and disk_free_pct."""
    return rules.check_device_status(device_id)


@tool
def reset_password(username: str) -> str:
    """Reset a user's password and send a temporary one to their registered email. Returns JSON."""
    return rules.reset_password(username)


@tool
def request_approval(username: str, device_id: str) -> str:
    """Raise an approval request for admin access for a user on a device. Returns JSON with the ticket."""
    return rules.request_approval(username, device_id)


@tool
def grant_admin_access(username: str, device_id: str) -> str:
    """Grant a user admin access on a device. Only call this once the approval request has been approved."""
    return rules.grant_admin_access(username, device_id)


HANDOFF_TOOLS = [transfer_to_diagnostics, transfer_to_actions]
DIAGNOSTICS_TOOLS = [check_device_status]
ACTIONS_TOOLS = [reset_password, request_approval, grant_admin_access]


class SimulatedHelpdeskModel(BaseChatModel):
    """Deterministic stand-in for an LLM: replays the transcript and asks rules.next_step what to do."""

    @property
    def _llm_type(self) -> str:
        return "simulated-helpdesk-rules"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "SimulatedHelpdeskModel":  # type: ignore[override]
        return self

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        system_prompt = next(str(m.content) for m in messages if isinstance(m, SystemMessage))
        request = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
        names: dict[str, str] = {}
        results: list[ToolResult] = []
        for message in messages:
            if isinstance(message, AIMessage):
                names.update({call["id"] or "": call["name"] for call in message.tool_calls})
            if isinstance(message, ToolMessage):
                ok = message.status != "error"
                results.append(ToolResult(names[message.tool_call_id], ok, str(message.content)))
        reply = next_step(system_prompt, request, results)
        metadata = {"model_name": self._llm_type}
        if isinstance(reply, ToolRequest):
            # Prefixed by role: the supervisor's and a worker's calls share the root transcript, so ids must differ.
            call_id = f"{rules.role_of(system_prompt)}-call-{len(results) + 1}"
            call = {"name": reply.name, "args": reply.arguments, "id": call_id, "type": "tool_call"}
            message = AIMessage(content="", tool_calls=[call], response_metadata=metadata)
        else:
            message = AIMessage(content=reply, response_metadata=metadata)
        return ChatResult(generations=[ChatGeneration(message=message)])


def _is_handoff(message: BaseMessage) -> bool:
    if isinstance(message, ToolMessage):
        return message.name in HANDOFF_TEAMS
    if isinstance(message, AIMessage) and message.tool_calls:
        return all(call["name"] in HANDOFF_TEAMS for call in message.tool_calls)
    return False


def _model_node(model: Any, system_prompt: str) -> Any:
    """A worker's model step. Handoff messages are dropped: they name tools the worker's model is not bound to."""

    def call_model(state: MessagesState) -> dict[str, list[BaseMessage]]:
        transcript = [m for m in state["messages"] if not _is_handoff(m)]
        return {"messages": [model.invoke([SystemMessage(system_prompt), *transcript])]}

    return call_model


def _after_tools(state: MessagesState) -> Literal["approval_gate", "model"]:
    last = state["messages"][-1]
    if isinstance(last, ToolMessage) and last.name == "request_approval" and last.status != "error":
        return "approval_gate"
    return "model"


def approval_gate(state: MessagesState) -> Command[Literal["model", "__end__"]]:
    """Pause for the approver. Resume with Command(resume={"approved": True}) to let the model grant access."""
    ticket = json.loads(str(state["messages"][-1].content))
    decision = interrupt({"action": "grant_admin_access", **ticket})
    if isinstance(decision, dict) and decision.get("approved") is True:
        return Command(goto="model")
    return Command(goto=END, update={"messages": [AIMessage(content=NOT_APPROVED)]})


def _diagnostics_worker(model: BaseChatModel) -> CompiledStateGraph:
    graph = StateGraph(MessagesState)
    graph.add_node("model", _model_node(model.bind_tools(DIAGNOSTICS_TOOLS), DIAGNOSTICS_PROMPT))
    # An unknown device raises in check_device_status; return it to the model rather than failing the case.
    graph.add_node("tools", ToolNode(DIAGNOSTICS_TOOLS, handle_tool_errors=True))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph.compile()


def _actions_worker(model: BaseChatModel, gated: bool) -> CompiledStateGraph:
    graph = StateGraph(MessagesState)
    graph.add_node("model", _model_node(model.bind_tools(ACTIONS_TOOLS), ACTIONS_PROMPT))
    graph.add_node("tools", ToolNode(ACTIONS_TOOLS, handle_tool_errors=True))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    if gated:
        graph.add_node("approval_gate", approval_gate)
        graph.add_conditional_edges("tools", _after_tools)
    else:
        graph.add_edge("tools", "model")
    return graph.compile()


def _supervisor_node(model: Any) -> Any:
    def supervisor(state: MessagesState) -> Command[Literal["diagnostics", "actions", "__end__"]]:
        reply = model.invoke([SystemMessage(SUPERVISOR_PROMPT), *state["messages"]])
        handoffs = [call for call in reply.tool_calls if call["name"] in HANDOFF_TEAMS]
        if not handoffs:
            return Command(goto=END, update={"messages": [reply]})
        # Every tool call needs a ToolMessage; only the first handoff is followed.
        team = HANDOFF_TEAMS[handoffs[0]["name"]]
        answers = [
            ToolMessage(
                content=f"Transferred to {team}." if n == 0 else "Not transferred: one team only.",
                name=call["name"],
                tool_call_id=call["id"],
            )
            for n, call in enumerate(handoffs)
        ]
        return Command(goto=team, update={"messages": [reply, *answers]})

    return supervisor


def _build(model: BaseChatModel, gated: bool = True) -> CompiledStateGraph:
    graph = StateGraph(MessagesState)
    graph.add_node("supervisor", _supervisor_node(model.bind_tools(HANDOFF_TOOLS)))
    graph.add_node("diagnostics", _diagnostics_worker(model))
    graph.add_node("actions", _actions_worker(model, gated))
    graph.add_edge(START, "supervisor")
    graph.add_edge("diagnostics", END)
    graph.add_edge("actions", END)
    return graph.compile(checkpointer=InMemorySaver())


def build_agent() -> CompiledStateGraph:
    return _build(SimulatedHelpdeskModel())


def build_ungated_agent() -> CompiledStateGraph:
    """The same agent after a refactor that wired the actions tool loop straight back to the model, so nothing
    pauses between request_approval and grant_admin_access."""
    return _build(SimulatedHelpdeskModel(), gated=False)


def build_live_agent() -> CompiledStateGraph:
    """The gated agent on a real model (needs langchain-aws and AWS credentials)."""
    from langchain_aws import ChatBedrockConverse

    return _build(ChatBedrockConverse(model=LIVE_MODEL_ID))
