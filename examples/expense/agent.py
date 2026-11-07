"""LangGraph expense-claim reviewer: a two-node graph (model, tools) with a simulated, rule-based chat model.

The model double reads the system prompt it is given and applies only the rules that prompt states, so the two
factories differ only in their prompt: build_agent uses PROMPT, build_condensed_agent uses PROMPT_CONDENSED.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from examples.expense import rules
from examples.expense.rules import PROMPT, PROMPT_CONDENSED, ToolRequest, ToolResult, next_step


@tool
def lookup_policy(category: str) -> str:
    """Return the expense policy for a category as JSON: the rule text and any limits in USD."""
    return rules.lookup_policy(category)


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies at the fixed company rates. Returns JSON with amount and currency."""
    return rules.convert_currency(amount, from_currency, to_currency)


@tool
def per_diem(city: str, days: int) -> str:
    """Return the meal per diem for a trip as JSON: daily_usd and total_usd."""
    return rules.per_diem(city, days)


TOOLS = [lookup_policy, convert_currency, per_diem]


class SimulatedReviewModel(BaseChatModel):
    """Deterministic stand-in for an LLM: replays the transcript and asks rules.next_step what to do."""

    @property
    def _llm_type(self) -> str:
        return "simulated-rule-engine"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "SimulatedReviewModel":  # type: ignore[override]
        return self

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        system_prompt = next(str(m.content) for m in messages if isinstance(m, SystemMessage))
        claim = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
        names: dict[str, str] = {}
        results: list[ToolResult] = []
        for message in messages:
            if isinstance(message, AIMessage):
                names.update({call["id"] or "": call["name"] for call in message.tool_calls})
            if isinstance(message, ToolMessage):
                ok = message.status != "error"
                results.append(ToolResult(names[message.tool_call_id], ok, str(message.content)))
        reply = next_step(system_prompt, claim, results)
        metadata = {"model_name": self._llm_type}
        if isinstance(reply, ToolRequest):
            call = {"name": reply.name, "args": reply.arguments, "id": f"call-{len(results) + 1}", "type": "tool_call"}
            message = AIMessage(content="", tool_calls=[call], response_metadata=metadata)
        else:
            message = AIMessage(content=reply, response_metadata=metadata)
        return ChatResult(generations=[ChatGeneration(message=message)])


def _build(system_prompt: str) -> CompiledStateGraph:
    model = SimulatedReviewModel().bind_tools(TOOLS)

    def call_model(state: MessagesState) -> dict[str, list[BaseMessage]]:
        return {"messages": [model.invoke([SystemMessage(system_prompt), *state["messages"]])]}

    graph = StateGraph(MessagesState)
    graph.add_node("model", call_model)
    # An unsupported currency raises in convert_currency; return it to the model rather than failing the case.
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph.compile()


def build_agent() -> CompiledStateGraph:
    return _build(PROMPT)


def build_condensed_agent() -> CompiledStateGraph:
    """The same agent after a prompt tidy-up that silently dropped the receipt rule."""
    return _build(PROMPT_CONDENSED)
