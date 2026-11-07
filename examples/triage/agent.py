"""LangGraph support-ticket triage: a classifier node routes to billing, technical or general specialists.

The state is a custom TypedDict with no `messages` channel, so aea needs the mapping hooks:
`--input-map examples.triage.agent:to_input --output-map examples.triage.agent:from_output`.
Tool calls are recorded in the `trail` channel (AIMessages tool calls and their ToolMessages) so they appear in the
graph's update events.

Only the classifier is a model. The offline double reads the classifier prompt it is given and applies only the
routing rules that prompt states, so the factories differ only in their prompt: build_agent uses PROMPT,
build_reworded_agent uses PROMPT_REWORDED. Specialists are deterministic and escalate high-priority billing tickets.
"""

import json
import os
import re
from typing import Annotated, Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from examples.triage import rules
from examples.triage.rules import CATEGORIES, PRIORITIES, PROMPT, PROMPT_REWORDED

LIVE_MODEL_ID = "us.anthropic.claude-haiku-5-5"

_INVOICE_ID = re.compile(r"\bINV-\d+\b")


@tool
def lookup_invoice(invoice_id: str) -> str:
    """Look up an invoice by id (for example INV-1001). Returns JSON with found, amount_usd, status and date."""
    return rules.lookup_invoice(invoice_id)


@tool
def search_known_issues(query: str) -> str:
    """Search the known-issues list. Returns a JSON list of matching issues with id, title and workaround."""
    return rules.search_known_issues(query)


@tool
def escalate_to_human(queue: str, priority: str, summary: str) -> str:
    """Hand a ticket to a human queue. Returns JSON with the escalation_id."""
    return rules.escalate_to_human(queue, priority, summary)


TOOLS = [lookup_invoice, search_known_issues, escalate_to_human]


class TriageState(TypedDict):
    message: str
    category: str
    priority: str
    reply: str
    # Tool-call trail only: the classifier's reply, each tool call and its result. Not the conversation.
    trail: Annotated[list[AnyMessage], add_messages]


class SimulatedTriageModel(BaseChatModel):
    """Deterministic stand-in for an LLM classifier: applies the routing rules its system prompt states."""

    @property
    def _llm_type(self) -> str:
        return "simulated-triage-classifier"

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        system_prompt = next(str(m.content) for m in messages if isinstance(m, SystemMessage))
        ticket = next(str(m.content) for m in messages if isinstance(m, HumanMessage))
        message = AIMessage(
            content=json.dumps(rules.classify(system_prompt, ticket)), response_metadata={"model_name": self._llm_type}
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def _parse_label(text: str) -> dict[str, str]:
    """Category and priority from the classifier's JSON reply; unknown or unparseable values fall back safely."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        label = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        label = {}
    if not isinstance(label, dict):
        label = {}
    category = label.get("category")
    priority = label.get("priority")
    return {
        "category": category if category in CATEGORIES else "other",
        "priority": priority if priority in PRIORITIES else "normal",
    }


def _call(node: str, step: int, tool_: BaseTool, args: dict[str, Any]) -> tuple[list[AnyMessage], Any]:
    """Run one tool call and return its trail entries (the call and its result) and the parsed result."""
    call_id = f"call-{node}-{step}"
    request = AIMessage(
        content="",
        id=f"{node}-request-{step}",
        tool_calls=[{"name": tool_.name, "args": args, "id": call_id, "type": "tool_call"}],
    )
    result: ToolMessage = tool_.invoke({"name": tool_.name, "args": args, "id": call_id, "type": "tool_call"})
    result.id = f"{node}-result-{step}"
    return [request, result], json.loads(result.text)


def billing(state: TriageState) -> dict[str, Any]:
    ticket = state["message"]
    if state["priority"] == "high":
        args = {"queue": "billing", "priority": "high", "summary": ticket}
        trail, result = _call("billing", 1, escalate_to_human, args)
        reply = (
            "I am sorry for the trouble. I have escalated this to our billing team as high priority "
            f"(reference {result['escalation_id']}). A specialist will contact you within 4 business hours."
        )
        return {"reply": reply, "trail": trail}
    invoice_id = next(iter(_INVOICE_ID.findall(ticket)), None)
    if invoice_id is None:
        return {"reply": "Please reply with your invoice number (it starts with INV-) so I can look into this."}
    trail, invoice = _call("billing", 1, lookup_invoice, {"invoice_id": invoice_id})
    if not invoice["found"]:
        reply = f"I could not find invoice {invoice_id}. Please check the number on your invoice email."
    elif invoice["status"] == "refunded":
        reply = (
            f"Invoice {invoice_id} was refunded on {invoice['date']}. "
            "Refunds take 5 to 10 business days to reach your card."
        )
    elif invoice["status"] == "overdue":
        reply = (
            f"Invoice {invoice_id} for {invoice['amount_usd']:.2f} USD is overdue. "
            "You can pay it from Billing > Invoices."
        )
    else:
        reply = f"Invoice {invoice_id} for {invoice['amount_usd']:.2f} USD was paid on {invoice['date']}."
    return {"reply": reply, "trail": trail}


def technical(state: TriageState) -> dict[str, Any]:
    trail, issues = _call("technical", 1, search_known_issues, {"query": state["message"]})
    if issues:
        issue = issues[0]
        reply = (
            f"This is a known issue ({issue['id']}: {issue['title']}). Workaround: {issue['workaround']} "
            "We will update you when the fix ships."
        )
    else:
        reply = "Thanks for the report. It does not match a known issue, so I have logged it for our engineers."
    return {"reply": reply, "trail": trail}


_ACCOUNT_REPLIES = (
    ("password", "You can reset your password from the sign-in page with Forgot password."),
    ("close my account", "You can close your account from Settings > Account > Close account."),
    ("profile", "You can update your profile details from Settings > Profile."),
)


def general(state: TriageState) -> dict[str, Any]:
    if state["category"] == "account":
        text = state["message"].lower()
        reply = next(
            (answer for phrase, answer in _ACCOUNT_REPLIES if phrase in text),
            "You can manage your account from Settings > Account.",
        )
    else:
        reply = "Thanks for getting in touch. Could you tell us a little more about what you need?"
    return {"reply": reply}


_ROUTES = {"billing": "billing", "technical": "technical", "account": "general", "other": "general"}


def _build(model: BaseChatModel, classifier_prompt: str) -> StateGraph:
    def classify(state: TriageState) -> dict[str, Any]:
        answer = model.invoke([SystemMessage(classifier_prompt), HumanMessage(state["message"])])
        answer.id = "classify-1"
        return {**_parse_label(answer.text), "trail": [answer]}

    graph = StateGraph(TriageState)
    graph.add_node("classify", classify)
    graph.add_node("billing", billing)
    graph.add_node("technical", technical)
    graph.add_node("general", general)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", lambda state: _ROUTES[state["category"]], sorted(set(_ROUTES.values())))
    for node in ("billing", "technical", "general"):
        graph.add_edge(node, END)
    return graph


def build_agent() -> CompiledStateGraph:
    return _build(SimulatedTriageModel(), PROMPT).compile()


def build_reworded_agent() -> CompiledStateGraph:
    """The same agent after a classifier-prompt tidy-up that dropped the urgent-billing rule."""
    return _build(SimulatedTriageModel(), PROMPT_REWORDED).compile()


def build_live_agent() -> StateGraph:
    """The good prompt on a real model, uncompiled (the adapter compiles a StateGraph). Needs AWS credentials."""
    from langchain_aws import ChatBedrockConverse

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    return _build(ChatBedrockConverse(model=LIVE_MODEL_ID, region_name=region), PROMPT)


def to_input(question: str) -> dict[str, Any]:
    """aea --input-map: the case input is the ticket text."""
    return {"message": question}


def from_output(state: dict[str, Any]) -> str:
    """aea --output-map: the answer is JSON with the triage fields, so dataset JSON checks apply."""
    return json.dumps({key: state.get(key) for key in ("category", "priority", "reply")})
