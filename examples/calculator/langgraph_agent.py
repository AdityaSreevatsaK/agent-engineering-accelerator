"""LangGraph version of the calculator agent: a two-node graph (model, tools) with a rule-based chat model double."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from examples.calculator.rules import (
    BROKEN_OPERATIONS,
    OPERATIONS,
    SYSTEM_PROMPT,
    ToolRequest,
    answer,
    calculate,
    decide,
)


@tool
def calculator(a: float, b: float, op: str) -> float:
    """Apply a basic arithmetic operation. op is one of add, sub, mul, div."""
    return calculate(a, b, op)


class RuleBasedChatModel(BaseChatModel):
    operations: dict[str, str]

    @property
    def _llm_type(self) -> str:
        return "rule-based-double"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "RuleBasedChatModel":  # type: ignore[override]
        return self

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        question = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
        last = messages[-1]
        if isinstance(last, ToolMessage):
            reply: ToolRequest | str = answer(question, str(last.content), failed=last.status == "error")
        else:
            reply = decide(question, self.operations)
        metadata = {"model_name": self._llm_type}
        if isinstance(reply, ToolRequest):
            call = {"name": "calculator", "args": reply.arguments, "id": "call-1", "type": "tool_call"}
            message = AIMessage(content="", tool_calls=[call], response_metadata=metadata)
        else:
            message = AIMessage(content=reply, response_metadata=metadata)
        return ChatResult(generations=[ChatGeneration(message=message)])


def _build(operations: dict[str, str]) -> CompiledStateGraph:
    model = RuleBasedChatModel(operations=operations).bind_tools([calculator])

    def call_model(state: MessagesState) -> dict[str, list[BaseMessage]]:
        return {"messages": [model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])]}

    graph = StateGraph(MessagesState)
    graph.add_node("model", call_model)
    # Strands returns tool errors to the model; LangGraph re-raises them unless asked not to.
    graph.add_node("tools", ToolNode([calculator], handle_tool_errors=True))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph.compile()


def build_agent() -> CompiledStateGraph:
    return _build(OPERATIONS)


def build_broken_agent() -> CompiledStateGraph:
    return _build(BROKEN_OPERATIONS)
