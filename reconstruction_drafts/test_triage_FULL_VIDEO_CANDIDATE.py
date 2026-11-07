import asyncio
import hashlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from inspect_ai.model import ModelOutput
from inspect_ai.solver import TaskState
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph

from agent_accelerator.adapters.langgraph import langgraph_agent
from agent_accelerator.compare import load_results

REPO = Path(__file__).resolve().parents[2]
# The examples are imported from the repo root, as `aea` does when it loads --agent and --input-map.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from examples.triage.agent import (  # noqa: E402
    SimulatedTriageModel,
    _parse_label,
    build_agent,
    build_live_agent,
    build_reworded_agent,
    from_output,
    to_input,
)
from examples.triage.rules import (  # noqa: E402
    ACCOUNT,
    BILLING,
    FALLBACK_SENTENCE,
    OUTAGE,
    PROMPT,
    PROMPT_REWORDED,
    TECHNICAL,
    URGENT_BILLING,
    classify,
)

DATASET = REPO / "examples" / "triage" / "dataset.jsonl"
GOLDEN = REPO / "examples" / "triage" / "golden.jsonl"
PLANTED = {"charged_twice_furious", "angry_invoice_dispute"}
MAP_FLAGS = ["--input-map", "examples.triage.agent:to_input", "--output-map", "examples.triage.agent:from_output"]


def _label(category, priority):
    return {"category": category, "priority": priority}


def _run(make, ticket):
    """The final state of one ticket through a fresh graph, as the adapter's input map builds it."""
    return make().invoke(to_input(ticket))


def _tools(state):
    """Tool names in call order, from the trail channel."""
    return [call["name"] for m in state["trail"] if isinstance(m, AIMessage) for call in m.tool_calls]


def _tool_args(state):
    return [call["args"] for m in state["trail"] if isinstance(m, AIMessage) for call in m.tool_calls]


def _answer(state):
    return json.loads(from_output(state))


def _escalation_reference(queue, priority, summary):
    # Derived from the documented scheme, not read from a run: ESC- and the first six hex digits, upper-cased.
    return "ESC-" + hashlib.sha256(f"{queue}|{priority}|{summary}".encode()).hexdigest()[:6].upper()


def _cases(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# rules.classify


@pytest.mark.parametrize(
    ("ticket", "category", "priority"),
    [
        ("I was double charged this month.", "billing", "high"),
        ("My invoice is wrong and I am angry.", "billing", "high"),
        ("Is there an outage right now?", "technical", "high"),
        ("When will my refund arrive?", "billing", "normal"),
        ("The app keeps crashing.", "technical", "normal"),
        ("Please change my profile photo.", "account", "normal"),
        ("Do you sell gift cards?", "other", "low"),
    ],
    ids=["duplicate_charge", "angry_billing", "outage", "refund", "crash", "profile", "fallback"],
)
def test_full_prompt_classifies_each_rule_by_its_trigger_phrases(ticket, category, priority):
    # Witness s40 urgent billing loses duplicate charge: `(("charged twice",), ("double charged",),` ->
    # `(("charged twice",),` (rules.py:65); the duplicate charge then reads as normal billing.
    # Witness s40 account rule dropped from prompt: `BILLING, TECHNICAL, ACCOUNT))` -> `BILLING, TECHNICAL))`
    # (rules.py:113); the profile ticket then falls back to other.
    assert classify(PROMPT, ticket) == _label(category, priority)


@pytest.mark.parametrize(
    ("ticket", "label"),
    [
        ("I am furious that the dashboard is so slow.", _label("technical", "normal")),
        ("THE DASHBOARD HAS AN OUTAGE.", _label("technical", "high")),
    ],
    ids=["anger_without_billing_word", "upper_case_ticket"],
)
def test_anger_alone_is_not_urgent_billing_and_matching_ignores_case(ticket, label):
    # Witness s40 anger alone is urgent: `tuple((billing, anger) for billing in BILLING_WORDS for anger in
    # _ANGER_WORDS)` -> `tuple((anger,) for anger in _ANGER_WORDS)` (rules.py:66).
    # Witness s40 trigger needs any phrase: `all(phrase in text for phrase in trigger)` -> `any(...)` (rules.py:159).
    # Witness s40 matching case-sensitive: `text = ticket.lower()` -> `text = ticket` (rules.py:157).
    assert classify(PROMPT, ticket) == label


def test_first_matching_rule_in_prompt_order_wins_whatever_the_rules_tuple_order():
    # The ticket matches both BILLING ("payment") and TECHNICAL ("login", "error").
    # Witness s40 rules in tuple order: `key=lambda rule: prompt.index(rule.sentence)` -> `key=RULES.index`
    # (rules.py:153); RULES lists BILLING first, so the technical-first prompt routes to billing.
    # Witness s40 last match wins: `for rule in active_rules(prompt):` -> `for rule in
    # reversed(active_rules(prompt)):` (rules.py:158).
    ticket = "Login error on the payment page."
    technical_first = f"{TECHNICAL.sentence} {BILLING.sentence}"
    billing_first = f"{BILLING.sentence} {TECHNICAL.sentence}"

    assert [classify(p, ticket) for p in (technical_first, billing_first, PROMPT, PROMPT_REWORDED)] == [
        _label("technical", "normal"),
        _label("billing", "normal"),
        _label("billing", "normal"),
        _label("technical", "normal"),
    ]


@pytest.mark.parametrize(
    ("prompt", "priority"),
    [(ACCOUNT.sentence, "normal"), (f"{ACCOUNT.sentence} {FALLBACK_SENTENCE}", "low")],
    ids=["no_fallback_sentence", "fallback_sentence"],
)
def test_unmatched_ticket_is_other_and_low_only_when_the_prompt_states_the_fallback(prompt, priority):
    # Witness s40 fallback always low: `"low" if FALLBACK_SENTENCE in prompt else "normal"` -> `"low"` (rules.py:161).
    assert classify(prompt, "Do you have an office in Lisbon?") == _label("other", priority)


# _parse_label


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ('```json\n{"category": "technical",\n "priority": "high"}\n```', _label("technical", "high")),
        ('Here it is: {"category": "account", "priority": "low"} thanks.', _label("account", "low")),
        ("billing, high", _label("other", "normal")),
        ("{category: billing}", _label("other", "normal")),
        ('{"category": "sales", "priority": "urgent"}', _label("other", "normal")),
        ('{"category": "billing"}', _label("billing", "normal")),
    ],
    ids=["fenced_multiline_json", "json_inside_prose", "not_json", "malformed_json", "out_of_set", "priority_missing"],
)
def test_classifier_reply_is_parsed_from_embedded_json_with_safe_fallbacks(text, label):
    # Witness s40 parse single line only: `text, re.DOTALL)` -> `text)` (agent.py:84).
    # Witness s40 parse no-match crashes: `json.loads(match.group(0)) if match else {}` -> `json.loads(match.group(0))`
    # (agent.py:86). Witness s40 parse decode error escapes: `except json.JSONDecodeError:` -> `except KeyError:`
    # (agent.py:87). Witness s40 parse category unchecked: `category if category in CATEGORIES else "other"` ->
    # `category or "other"` (agent.py:94). Witness s40 parse priority unchecked: `priority if priority in PRIORITIES
    # else "normal"` -> `priority or "normal"` (agent.py:95).
    assert _parse_label(text) == label


# routing and specialists


@pytest.mark.parametrize(
    ("ticket", "category", "priority", "reply", "tools"),
    [
        (
            "Why is invoice INV-1003 still open?",
            "billing",
            "normal",
            "Invoice INV-1003 for 99.00 USD is overdue. You can pay it from Billing > Invoices.",
            ["lookup_invoice"],
        ),
        (
            "The reports page is slow today.",
            "technical",
            "normal",
            "Thanks for the report. It does not match a known issue, so I have logged it for our engineers.",
            ["search_known_issues"],
        ),
        (
            "How do I edit my profile?",
            "account",
            "normal",
            "You can update your profile details from Settings > Profile.",
            [],
        ),
        (
            "Can I visit your office?",
            "other",
            "low",
            "Thanks for getting in touch. Could you tell us a little more about what you need?",
            [],
        ),
    ],
)
def test_each_category_is_routed_to_its_specialist(ticket, category, priority, reply, tools):
    state = _run(build_agent, ticket)
    assert _answer(state) == {"category": category, "priority": priority, "reply": reply}
    assert _tools(state) == tools


def test_high_priority_billing_ticket_is_escalated_with_the_ticket_as_summary_and_quotes_the_reference():
    # Witness s40 escalation summary dropped: `"summary": ticket` -> `"summary": ""` (agent.py:115).
    # Witness s40 escalation reference length: `.hexdigest()[:6]` -> `.hexdigest()[:8]` (rules.py:146).
    ticket = "I was double charged for INV-1001 and I want it fixed."
    state = _run(build_agent, ticket)

    reference = _escalation_reference("billing", "high", ticket)
    assert _answer(state) == {
        "category": "billing",
        "priority": "high",
        "reply": "I am sorry for the trouble. I have escalated this to our billing team as high priority "
        f"(reference {reference}). A specialist will contact you within 4 business hours.",
    }
    assert _tool_args(state) == [{"queue": "billing", "priority": "high", "summary": ticket}]


@pytest.mark.parametrize(
    ("ticket", "label", "tools"),
    [
        ("Is there an outage on the dashboard?", _label("technical", "high"), ["search_known_issues"]),
        ("Has invoice INV-1001 been paid?", _label("billing", "normal"), ["lookup_invoice"]),
    ],
    ids=["technical_high", "billing_normal"],
)
def test_only_billing_at_high_priority_is_escalated(ticket, label, tools):
    # Witness s40 billing escalates normal: `if state["priority"] == "high":` -> `if state["priority"] != "low":`
    # (agent.py:114). Witness s40 technical routed to billing: `"technical": "technical",` -> `"technical": "billing",`
    # (agent.py:175); the high-priority outage then reaches billing and is escalated.
    state = _run(build_agent, ticket)

    assert {key: state[key] for key in ("category", "priority")} == label
    assert _tools(state) == tools


# mapping hooks


def test_input_map_writes_only_the_ticket_and_output_map_returns_only_the_three_answer_fields():
    # Witness s40 input map adds a key: `return {"message": question}` -> `return {"message": question, "reply": ""}`
    # (agent.py:215). Witness s40 output map drops priority: `for key in ("category", "priority", "reply")` ->
    # `for key in ("category", "reply")` (agent.py:220). Witness s40 output map requires keys: `state.get(key)` ->
    # `state[key]` (agent.py:220).
    full = {"message": "m", "category": "billing", "priority": "high", "reply": "r", "trail": [AIMessage("x")]}

    assert to_input("Where is my refund?") == {"message": "Where is my refund?"}
    assert json.loads(from_output(full)) == {"category": "billing", "priority": "high", "reply": "r"}
    assert json.loads(from_output({"message": "m"})) == {"category": None, "priority": None, "reply": None}


def _solve(input_map):
    solve = langgraph_agent("examples.triage.agent:build_agent", input_map, "examples.triage.agent:from_output")
    state = TaskState(
        model="test-model",
        sample_id="triage",
        epoch=1,
        input="How do I reset my password?",
        messages=[],
        output=ModelOutput(completion=""),
    )
    return asyncio.run(solve(state, None))


def test_graph_has_no_messages_channel_so_the_adapter_needs_the_input_map():
    # Witness s40 graph gains messages channel: `reply: str\n` -> `reply: str\n    messages:
    # Annotated[list[AnyMessage], add_messages]\n` (agent.py:59); the adapter then sends the question as messages,
    # the classifier finds no `message` and the error no longer names --input-map.
    unmapped = _solve(None)
    mapped = _solve("examples.triage.agent:to_input")

    assert "messages" not in build_agent().channels
    assert unmapped.metadata["agent_error"].startswith("MissingInputMapError:")
    assert "--input-map" in unmapped.metadata["agent_error"]
    assert mapped.metadata["agent_error"] is None
    assert json.loads(mapped.output.completion)["reply"].startswith("You can reset your password")


# the regression and the factories


@pytest.mark.parametrize(
    ("make", "charged_twice", "angry_invoice"),
    [
        (
            build_agent,
            (_label("billing", "high"), ["escalate_to_human"]),
            (_label("billing", "high"), ["escalate_to_human"]),
        ),
        (
            build_reworded_agent,
            (_label("technical", "normal"), ["search_known_issues"]),
            (_label("billing", "normal"), ["lookup_invoice"]),
        ),
    ],
    ids=["good_prompt", "reworded_prompt"],
)
def test_reworded_agent_routes_the_planted_tickets_away_from_escalation(make, charged_twice, angry_invoice):
    # Witness s40 reworded keeps urgent billing: `(OUTAGE, TECHNICAL_REWORDED, BILLING, ACCOUNT)` ->
    # `(URGENT_BILLING, OUTAGE, TECHNICAL_REWORDED, BILLING, ACCOUNT)` (rules.py:123).
    # Witness s40 build_agent uses reworded: `_build(SimulatedTriageModel(), PROMPT).compile()` ->
    # `_build(SimulatedTriageModel(), PROMPT_REWORDED).compile()` (agent.py:197).
    tickets = [json.loads(line)["input"] for line in DATASET.read_text(encoding="utf-8").splitlines()[:2]]
    results = []
    for ticket in tickets:
        state = _run(make, ticket)
        results.append(({key: state[key] for key in ("category", "priority")}, _tools(state)))

    assert results == [charged_twice, angry_invoice]


def test_simulated_classifier_follows_the_prompt_it_is_given_not_the_factory():
    # Adding the urgent-billing sentence back to the reworded prompt restores the escalation route, so the
    # regression is carried by the prompt text alone.
    # Witness s40 double ignores system prompt: `system_prompt = next(str(m.content) for m in messages if
    # isinstance(m, SystemMessage))` -> `system_prompt = PROMPT` (agent.py:74).
    # Witness s40 build_reworded_agent uses good prompt: `_build(SimulatedTriageModel(), PROMPT_REWORDED)` ->
    # `_build(SimulatedTriageModel(), PROMPT)` (agent.py:202); the reworded factory then escalates.
    ticket = "I was charged twice and I'm furious."
    model = SimulatedTriageModel()
    prompts = [PROMPT, PROMPT_REWORDED, f"{URGENT_BILLING.sentence} {PROMPT_REWORDED}", OUTAGE.sentence]

    labels = [json.loads(model.invoke([SystemMessage(p), HumanMessage(ticket)]).text) for p in prompts]
    reworded = _run(build_reworded_agent, ticket)

    assert labels == [
        _label("billing", "high"),
        _label("technical", "normal"),
        _label("billing", "high"),
        _label("other", "normal"),
    ]
    assert (reworded["category"], _tools(reworded)) == ("technical", ["search_known_issues"])


# live agent


def test_importing_the_agent_does_not_import_langchain_aws():
    # A subprocess: this test process may already have langchain_aws loaded.
    # Witness s40 eager bedrock import: `import json\nimport os\n` -> `import json\nimport os\nimport langchain_aws\n`
    # (agent.py:13-14).
    code = "import sys; import examples.triage.agent; print('langchain_aws' in sys.modules)"
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, env={**os.environ, "PYTHONUTF8": "1"}, capture_output=True, text=True
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"


@pytest.mark.parametrize(
    ("region", "default_region", "expected"),
    [("eu-west-1", "ap-south-1", "eu-west-1"), (None, "ap-south-1", "ap-south-1"), (None, None, "us-east-1")],
    ids=["aws_region_first", "default_region_second", "us_east_1_last"],
)
def test_live_agent_builds_an_uncompiled_graph_on_bedrock_with_the_region_from_the_environment(
    monkeypatch, region, default_region, expected
):
    # Witness s40 live region precedence: `os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")` ->
    # `os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")` (agent.py:209).
    # Witness s40 live agent compiled: `region_name=region), PROMPT)` -> `region_name=region), PROMPT).compile()` (agent.py:210).
    # Claude Haiku 5.5 on Bedrock rejects `temperature`, so the kwargs are exactly the model id and the region.
    # Witness s44 triage live temperature: `region_name=region)` -> `region_name=region, temperature=0)` (agent.py:210).
    received = []

    class FakeBedrock:
        def __init__(self, **kwargs):
            received.append(kwargs)

    monkeypatch.setitem(sys.modules, "langchain_aws", types.SimpleNamespace(ChatBedrockConverse=FakeBedrock))
    for name, value in (("AWS_REGION", region), ("AWS_DEFAULT_REGION", default_region)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    graph = build_live_agent()

    assert type(graph) is StateGraph
    assert received == [{"model": "us.anthropic.claude-haiku-5-5", "region_name": expected}]


# golden and dataset


def test_golden_has_six_references_five_labelled_each_matching_the_good_agents_answer():
    # Witness s40 refund timeline reworded: `Refunds take 5 to 10 business days to reach your card.` ->
    # `Refunds take 3 to 5 business days to reach your card.` (agent.py:131).
    # Witness s40 paid amount format: `{invoice['amount_usd']:.2f} USD was paid` -> `{invoice['amount_usd']:.1f} USD
    # was paid` (agent.py:139).
    inputs = {case["id"]: case["input"] for case in _cases(DATASET)}
    golden = _cases(GOLDEN)
    golden_by_id = {entry["id"]: entry["reference"] for entry in golden}
    answers = {entry["id"]: _answer(_run(build_agent, inputs[entry["id"]])) for entry in golden}
    mismatched = {key: answer for key, answer in answers.items() if answer != json.loads(golden_by_id[key])}

    assert len(golden) == 6
    assert sum("label" in entry for entry in golden) == 5
    assert mismatched == {}


@pytest.mark.slow
@pytest.mark.parametrize(
    ("factory", "failing"),
    [("build_agent", set()), ("build_reworded_agent", PLANTED)],
    ids=["good_prompt", "reworded_prompt"],
)
def test_dataset_run_passes_with_the_good_prompt_and_fails_only_the_planted_cases_when_reworded(
    tmp_path, factory, failing
):
    # A subprocess, as in test_cli.py: the tracer provider can only be set once per process.
    # Witness s40 reworded keeps urgent billing (as above): the reworded run then passes every case.
    # Witness s40 build_agent uses reworded (as above): the good run then fails the planted cases.
    command = [sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET), "--adapter", "langgraph"]
    command += ["--agent", f"examples.triage.agent:{factory}", *MAP_FLAGS, "--runs-dir", str(tmp_path)]
    env = {**os.environ, "PYTHONUTF8": "1"}
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr

    (run_dir,) = tmp_path.iterdir()
    results = load_results(run_dir)

    assert len(results.cases) == 12
    assert {case_id for case_id, case in results.cases.items() if not case.passed} == failing
