"""LangGraph policy Q&A with agentic RAG: decide, retrieve (ToolNode), grade, a bounded rewrite loop, and answer.

decide either calls search_policy or answers; the grade edge keeps the retrieved chunks whose topic matches the
query, sending the run to answer if any are relevant and otherwise to rewrite (at most MAX_REWRITES times, then to
answer, which says the question is not covered). The model double reads the system prompt it is given and applies
only the rules that prompt states, so the offline factories differ only in their prompt: build_agent uses PROMPT,
build_confident_agent uses PROMPT_CONFIDENT. Grading and rewriting are plain code in every factory.
"""

from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from examples.policy_rag import rules
from examples.policy_rag.rules import MAX_REWRITES, PROMPT, PROMPT_CONFIDENT, Search

LIVE_MODEL_ID = "us.anthropic.claude-haiku-5-5"


@tool
def search_policy(query: str) -> str:
    """Search the travel and expense policy. Returns JSON: up to two chunks, each with section id, title and text."""
    return rules.search_policy(query)


TOOLS = [search_policy]


class SimulatedPolicyModel(BaseChatModel):
    """Deterministic stand-in for an LLM: reads the transcript and asks rules.decide or rules.answer what to say."""

    @property
    def _llm_type(self) -> str:
        return "simulated-policy-rag"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "SimulatedPolicyModel":  # type: ignore[override]
        return self

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        system_prompt = next(str(m.content) for m in messages if isinstance(m, SystemMessage))
        query = next(str(m.content) for m in reversed(messages) if isinstance(m, HumanMessage))
        metadata = {"model_name": self._llm_type}
        chunks = rules.parse_answer_request(query)
        searches = sum(isinstance(m, ToolMessage) for m in messages)
        step = (
            rules.answer(system_prompt, chunks)
            if chunks is not None
            else rules.decide(system_prompt, query, searches > 0)
        )
        if isinstance(step, Search):
            call = {
                "name": "search_policy",
                "args": {"query": step.query},
                "id": f"call-{searches + 1}",
                "type": "tool_call",
            }
            message = AIMessage(content="", tool_calls=[call], response_metadata=metadata)
        else:
            message = AIMessage(content=step, response_metadata=metadata)
        return ChatResult(generations=[ChatGeneration(message=message)])


def _current_query(messages: Sequence[BaseMessage]) -> str:
    """The question being searched for: the original, or the latest rewrite of it."""
    return next(m.text for m in reversed(messages) if isinstance(m, HumanMessage))


def _latest_results(messages: Sequence[BaseMessage]) -> list[str]:
    """ToolMessage contents from the most recent retrieve step."""
    results: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            break
        results.insert(0, message.text)
    return results


def _relevant(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    return rules.relevant_chunks(_current_query(messages), _latest_results(messages))


def _build(model: BaseChatModel, system_prompt: str) -> CompiledStateGraph:
    with_tools = model.bind_tools(TOOLS)

    def decide(state: MessagesState) -> dict[str, list[BaseMessage]]:
        return {"messages": [with_tools.invoke([SystemMessage(system_prompt), *state["messages"]])]}

    def grade(state: MessagesState) -> Literal["answer", "rewrite"]:
        rewrites = sum(isinstance(m, HumanMessage) for m in state["messages"]) - 1
        return "answer" if _relevant(state["messages"]) or rewrites >= MAX_REWRITES else "rewrite"

    def rewrite(state: MessagesState) -> dict[str, list[BaseMessage]]:
        return {"messages": [HumanMessage(rules.rewrite_query(_current_query(state["messages"])))]}

    def answer(state: MessagesState) -> dict[str, list[BaseMessage]]:
        # Only graded-relevant chunks reach the answer; a fresh request keeps tool blocks out of the model call.
        question = next(m.text for m in state["messages"] if isinstance(m, HumanMessage))
        request = HumanMessage(rules.answer_request(question, _relevant(state["messages"])))
        return {"messages": [model.invoke([SystemMessage(system_prompt), request])]}

    graph = StateGraph(MessagesState)
    graph.add_node("decide", decide)
    graph.add_node("retrieve", ToolNode(TOOLS, handle_tool_errors=True))
    graph.add_node("rewrite", rewrite)
    graph.add_node("answer", answer)
    graph.add_edge(START, "decide")
    graph.add_conditional_edges("decide", tools_condition, {"tools": "retrieve", END: END})
    graph.add_conditional_edges("retrieve", grade)
    graph.add_edge("rewrite", "decide")
    graph.add_edge("answer", END)
    return graph.compile()


def build_agent() -> CompiledStateGraph:
    return _build(SimulatedPolicyModel(), PROMPT)


def build_confident_agent() -> CompiledStateGraph:
    """The same agent after a latency tweak: answer directly when confident, and no longer always search."""
    return _build(SimulatedPolicyModel(), PROMPT_CONFIDENT)


def build_live_agent() -> CompiledStateGraph:
    """The good prompt on a real model through Amazon Bedrock. Needs langchain-aws and AWS credentials."""
    from langchain_aws import ChatBedrockConverse  # pyright: ignore[reportMissingImports]

    return _build(ChatBedrockConverse(model=LIVE_MODEL_ID), PROMPT)
