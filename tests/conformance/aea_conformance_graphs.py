"""One tiny offline LangGraph graph per shape the adapter supports, driven by fake chat models (no credentials).

Every factory builds a fresh graph, and so a fresh scripted model, per call, as `--agent` requires.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from pydantic import BaseModel


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def grant_admin(user: str) -> str:
    """Grant a user admin rights."""
    return f"{user} is now an admin"


def call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def scripted(*turns: AIMessage) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter(turns))


def adds_one_and_two() -> GenericFakeChatModel:
    return scripted(call("add", {"a": 1, "b": 2}, "c1"), AIMessage("3"))


def react(state_schema: type = MessagesState, model_node=None) -> StateGraph:
    """model -> tools -> model until the model stops calling tools, the shape of a ReAct agent."""
    model = adds_one_and_two()
    graph = StateGraph(state_schema)
    graph.add_node("model", model_node or (lambda state: {"messages": [model.invoke(state["messages"])]}))
    graph.add_node("tools", ToolNode([add]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph


def single(state_schema: type, node) -> StateGraph:
    graph = StateGraph(state_schema)
    graph.add_node("only", node)
    graph.add_edge(START, "only")
    graph.add_edge("only", END)
    return graph


# MessagesState ReAct agent.
def messages_react():
    return react().compile()


# The shape langchain.agents.create_agent compiles (langchain is not installed here): AgentState with messages and
# structured_response, a model node and a ToolNode, the structured answer set when the model stops calling tools.
class Total(BaseModel):
    total: int


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    structured_response: Any


def create_agent_style():
    model = adds_one_and_two()

    def model_node(state):
        reply = model.invoke(state["messages"])
        return (
            {"messages": [reply]} if reply.tool_calls else {"messages": [reply], "structured_response": Total(total=3)}
        )

    return react(AgentState, model_node).compile()


# Custom state with no messages channel, adapted with --input-map and --output-map.
class Ticket(TypedDict):
    text: str
    category: str


def ticket_triage():
    return single(
        Ticket, lambda state: {"category": "billing" if "charged" in state["text"] else "technical"}
    ).compile()


def to_ticket(question: str) -> dict[str, str]:
    return {"text": question}


def category_of(state: dict[str, Any]) -> str:
    return state["category"]


# Functional API: an @entrypoint is a Pregel, given its input by --input-map.
def functional():
    @entrypoint()
    def run(inputs: dict[str, str]) -> dict[str, list]:
        result = add.invoke({"a": 1, "b": 2})
        return {"messages": [call("add", {"a": 1, "b": 2}, "f1"), AIMessage(f"{inputs['question']} = {result}")]}

    return run


def to_question(question: str) -> dict[str, str]:
    return {"question": question}


# Supervisor delegating to a worker subgraph whose tool call happens inside the subgraph.
def supervisor_with_worker():
    worker = react().compile()
    graph = StateGraph(MessagesState)
    graph.add_node("worker", worker)
    graph.add_node(
        "supervisor", lambda state: {"messages": [AIMessage("the worker says " + state["messages"][-1].text)]}
    )
    graph.add_edge(START, "worker")
    graph.add_edge("worker", "supervisor")
    graph.add_edge("supervisor", END)
    return graph.compile()


# An uncompiled StateGraph, as create_supervisor and create_swarm return.
def uncompiled_builder():
    return react()


# A checkpointer compiled in, which needs a thread_id to run at all.
def with_checkpointer():
    return react().compile(checkpointer=InMemorySaver())


# An approval gate: interrupt() before the privileged tool.
def approval_gate():
    def gate(state):
        approved = interrupt({"approve": "grant_admin for user-7?"})
        return {"messages": [call("grant_admin", {"user": "user-7"}, "g1")] if approved else []}

    graph = StateGraph(MessagesState)
    graph.add_node("gate", gate)
    graph.add_node("tools", ToolNode([grant_admin]))
    graph.add_edge(START, "gate")
    graph.add_edge("gate", "tools")
    graph.add_edge("tools", END)
    return graph.compile(checkpointer=InMemorySaver())


# Async-only nodes, which fail under a synchronous invoke.
def async_only():
    model = adds_one_and_two()

    async def model_node(state):
        return {"messages": [await model.ainvoke(state["messages"])]}

    return react(model_node=model_node).compile()


# A final answer in content blocks, as Claude on Bedrock returns it.
def content_blocks():
    blocks = [{"type": "text", "text": "The capital is "}, {"type": "text", "text": "Paris."}]
    return single(MessagesState, lambda state: {"messages": [AIMessage(content=blocks)]}).compile()


# A structured_response given as a dict.
def structured_dict():
    return single(
        AgentState, lambda state: {"messages": [AIMessage("ignored")], "structured_response": {"capital": "Paris"}}
    ).compile()


# A graph that adds no AI message.
def adds_no_ai_message():
    return single(MessagesState, lambda state: {}).compile()
