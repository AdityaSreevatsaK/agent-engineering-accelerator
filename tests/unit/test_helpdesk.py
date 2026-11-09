import asyncio
import json
import os
import subprocess
import sys
import types
import uuid
from pathlib import Path

import pytest
from inspect_ai.model import ModelOutput
from inspect_ai.solver import TaskState
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from agent_accelerator.adapters.langgraph import langgraph_agent
from agent_accelerator.compare import load_results

REPO = Path(__file__).resolve().parents[2]
# The examples are imported from the repo root, as `aea` does when it loads --agent and --scorer.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from examples.helpdesk.agent import (  # noqa: E402
    LIVE_MODEL_ID,
    SimulatedHelpdeskModel,
    build_agent,
    build_live_agent,
    build_ungated_agent,
)
from examples.helpdesk.rules import (  # noqa: E402
    DIAGNOSTICS_PROMPT,
    NO_DEVICE,
    NO_USER,
    NOT_APPROVED,
    OUT_OF_SCOPE,
    ToolResult,
    check_device_status,
    grant_admin_access,
    next_step,
    request_approval,
    reset_password,
)

DATASET = REPO / "examples" / "helpdesk" / "dataset.jsonl"
GOLDEN = REPO / "examples" / "helpdesk" / "golden.jsonl"
ADMIN_CASES = {"admin_local_docker", "admin_driver_update"}
DOCKER = "Please grant local admin rights to user bchen on LT-2001 so they can install Docker."
GRANTED = "Admin access on LT-2001 has been granted to bchen."
TICKET = {"ticket": "APR-LT-2001-bchen", "status": "pending", "approver": "IT security"}


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _thread():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def _invoke(make, text):
    return make().invoke({"messages": [HumanMessage(text)]}, _thread())


def _calls(messages):
    return [call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]


def _solve(factory, text):
    """Runs one case through the real LangGraph adapter solver, as `aea run` does."""
    state = TaskState(
        model="test-model", sample_id="helpdesk", epoch=1, input=text, messages=[], output=ModelOutput(completion="")
    )
    return asyncio.run(langgraph_agent(f"examples.helpdesk.agent:{factory}")(state, None))


def _aea_run(tmp_path, factory, *extra):
    # A subprocess, as in test_cli.py: the tracer provider can only be set once per process.
    command = [sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET), "--adapter", "langgraph"]
    command += ["--agent", f"examples.helpdesk.agent:{factory}", "--runs-dir", str(tmp_path), *extra]
    env = {**os.environ, "PYTHONUTF8": "1"}
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr
    (run_dir,) = tmp_path.iterdir()
    return load_results(run_dir)


# tools

@pytest.mark.parametrize(
    ("device_id", "online", "disk"),
    [("LT-1042", True, 7), ("LT-2001", False, 41), ("DT-3300", True, 63)],
    ids=["lt_1042", "lt_2001", "dt_3300"],
)
def test_check_device_status_returns_the_directory_entry_with_its_id(device_id, online, disk):
    # Witness s42 device status drops the id (rules.py:82).
    status = json.loads(check_device_status(device_id))

    assert (status["device_id"], status["online"], status["disk_free_pct"]) == (device_id, online, disk)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: check_device_status("LT-9999"), "^unknown device$"),
        (lambda: reset_password("mlopez"), "^unknown user$"),
        (lambda: request_approval("mlopez", "LT-2001"), "^unknown user or device$"),
        (lambda: request_approval("bchen", "LT-9999"), "^unknown user or device$"),
        (lambda: grant_admin_access("bchen", "LT-9999"), "^unknown user or device$"),
    ],
    ids=["device", "password_user", "approval_user", "approval_device", "grant_device"],
)
def test_tools_reject_an_unknown_device_or_user_without_echoing_it(call, message):
    # Witness s42 approval device unchecked (rules.py:92).
    with pytest.raises(ValueError, match=message):
        call()


def test_password_reset_and_approval_return_their_records_for_a_known_user():
    # Witness s42 approval ticket names (rules.py:94).
    assert json.loads(reset_password("asmith")) == {
        "username": "asmith",
        "status": "reset",
        "delivery": "registered email",
    }
    assert json.loads(request_approval("bchen", "LT-2001")) == TICKET


# diagnostics

@pytest.mark.parametrize(("disk", "warned"), [(9, True), (10, False)], ids=["just_under_threshold", "at_threshold"])
def test_low_disk_warning_is_given_only_below_10_percent_free(disk, warned):
    # Witness s42 low disk boundary (rules.py:189).
    output = json.dumps(
        {"device_id": "DT-3300", "online": True, "last_seen": "t", "os": "Ubuntu", "disk_free_pct": disk}
    )
    reply = next_step(DIAGNOSTICS_PROMPT, "check DT-3300", [ToolResult("check_device_status", True, output)])

    warning = f" Warning: low disk space, only {disk}% free, which can slow it down." if warned else ""
    assert reply == f"DT-3300 is online, last seen t, running Ubuntu.{warning}"


@pytest.mark.parametrize(
    ("text", "reply", "calls"),
    [
        (
            "Can you check the status of laptop LT-1042? It feels really slow.",
            "LT-1042 is online, last seen 2026-10-22T09:14Z, running Windows 11 24H2. Warning: low disk space, only 7% "
            "free, which can slow it down.",
            ["transfer_to_diagnostics", "check_device_status"],
        ),
        (
            "My laptop LT-2001 will not connect to the VPN.",
            "LT-2001 is offline, last seen 2026-10-19T17:02Z, running Windows 11 24H2.",
            ["transfer_to_diagnostics", "check_device_status"],
        ),
        (
            "Please check device LT-9999, it will not boot.",
            "I could not find device LT-9999 in the asset inventory. Please check the ID.",
            ["transfer_to_diagnostics", "check_device_status"],
        ),
        ("My laptop keeps freezing, can you take a look?", NO_DEVICE, ["transfer_to_diagnostics"]),
    ],
    ids=["online_low_disk", "offline", "unknown_device", "no_device_id"],
)
def test_device_questions_go_to_diagnostics_which_reports_the_status_or_the_tool_error(text, reply, calls):
    # Witness s42 tool errors ok and device routed to actions (agent.py:105 and rules.py:167).
    messages = _invoke(build_agent, text)["messages"]

    assert (messages[-1].content, _calls(messages)) == (reply, calls)


# actions: password

@pytest.mark.parametrize(
    ("text", "reply", "calls"),
    [
        (
            "I am locked out. Please reset the password for user asmith.",
            "The password for asmith has been reset; a temporary password was sent to their registered email.",
            ["transfer_to_actions", "reset_password"],
        ),
        (
            "Reset the password for user mlopez please.",
            "I could not find user mlopez in the directory, so no password was reset.",
            ["transfer_to_actions", "reset_password"],
        ),
        ("Please reset my password.", NO_USER, ["transfer_to_actions"]),
    ],
    ids=["known_user", "unknown_user", "no_user"],
)
def test_password_requests_go_to_actions_which_resets_or_reports_the_unknown_user(text, reply, calls):
    # Witness s42 password reset ignores failure (rules.py).
    messages = _invoke(build_agent, text)["messages"]

    assert (messages[-1].content, _calls(messages)) == (reply, calls)


# supervisor

@pytest.mark.parametrize(
    "text",
    ["Can you book a meeting room for Friday afternoon?", "What is the meal per diem for a trip to London?"],
    ids=["meeting_room", "expenses"],
)
def test_request_that_is_not_it_support_is_declined_by_the_supervisor_with_no_tool_call(text):
    # Witness s42 out of scope routed (rules.py:166).
    messages = _invoke(build_agent, text)["messages"]

    assert [(type(m).__name__, m.content) for m in messages] == [
        ("HumanMessage", text), ("AIMessage", OUT_OF_SCOPE)
    ]
    assert _calls(messages) == []


# the approval gate

def test_gated_agent_pauses_after_request_approval_with_the_ticket_and_never_grants():
    # Witness s42 interrupt payload drops ticket (agent.py:147).
    agent = build_agent()
    config = _thread()
    result = agent.invoke({"messages": [HumanMessage(DOCKER)]}, config)
    # Actions worker is still in its checkpoint, not yet the root's messages.
    (task,) = agent.get_state(config, subgraphs=True).tasks

    (pending,) = result["__interrupt__"]
    assert pending.value == {"action": "grant_admin_access", **TICKET}
    assert (task.name, task.state.next) == ("actions", ("approval_gate",))
    assert _calls(task.state.values["messages"]) == ["transfer_to_actions", "request_approval"]


@pytest.mark.parametrize(
    ("decision", "reply", "calls"),
    [
        ({"approved": True}, GRANTED, ["transfer_to_actions", "request_approval", "grant_admin_access"]),
        ({"approved": False}, NOT_APPROVED, ["transfer_to_actions", "request_approval"]),
        ({"approved": "true"}, NOT_APPROVED, ["transfer_to_actions", "request_approval"]),
        (True, NOT_APPROVED, ["transfer_to_actions", "request_approval"]),
    ],
    ids=["approved", "rejected", "approved_as_string", "not_a_dict"],
)
def test_resuming_the_same_thread_grants_only_on_an_explicit_approval(decision, reply, calls):
    # Witness s42 approved resume ends and truthy approval accepted (agent.py:148).
    agent = build_agent()
    config = _thread()
    agent.invoke({"messages": [HumanMessage(DOCKER)]}, config)

    result = agent.invoke(Command(resume=decision), config)

    assert "__interrupt__" not in result
    assert (result["messages"][-1].content, _calls(result["messages"])) == (reply, calls)


def test_gate_is_a_graph_difference_between_two_agents_sharing_model_prompts_and_tools():
    # The approved gated run and ungated run give the same transcript; only the graph differs.
    # Witness s42 ungated factory gated (agent.py:217).
    gated, ungated = build_agent(), build_ungated_agent()
    nodes = [set(graph.get_graph(xray=True).nodes) for graph in (gated, ungated)]
    config = _thread()
    gated.invoke({"messages": [HumanMessage(DOCKER)]}, config)
    approved = gated.invoke(Command(resume={"approved": True}), config)["messages"]
    straight = ungated.invoke({"messages": [HumanMessage(DOCKER)]}, _thread())["messages"]

    assert nodes[0] - nodes[1] == {"actions:approval_gate"}
    assert nodes[1] <= nodes[0]
    assert [(type(m).__name__, m.content) for m in approved] == [
        (type(m).__name__, m.content) for m in straight
    ]
    assert straight[-1].content == GRANTED


def test_a_failed_approval_request_does_not_pause_the_run():
    # Witness s42 gate on failed approval (agent.py:139).
    result = _invoke(build_agent, "Give user mlopez admin access on LT-2001.")

    assert "__interrupt__" not in result
    assert (
        result["messages"][-1].content
        == "I could not raise an approval for mlopez on LT-2001, so no access was granted."
    )
    assert [m.status for m in result["messages"] if isinstance(m, ToolMessage)] == ["success", "error"]


# through the adapter solver

def test_adapter_records_an_interrupted_admin_case_with_an_empty_answer_and_each_tool_call_once():
    # Actions worker stops at the gate, so its calls come from subgraph updates alone.
    # Witness s42 adapter interrupt not detected (adapters/langgraph.py:83).
    state = _solve("build_agent", DOCKER)

    assert (state.metadata["interrupted"], state.output.completion) == (True, "")
    assert state.metadata["tool_calls"] == [
        {"name": "transfer_to_actions", "arguments": {}},
        {"name": "request_approval", "arguments": {"username": "bchen", "device_id": "LT-2001"}},
    ]
    assert state.metadata["tool_errors"] == [False, False]
    assert [(m.function, m.text) for m in state.messages if hasattr(m, "function")] == [
        ("transfer_to_actions", "Transferred to actions."),
        ("request_approval", json.dumps(TICKET)),
    ]


def test_adapter_records_each_subgraph_tool_call_once_with_its_own_error_status():
    # Witness s42 adapter dedupe off and worker call ids collide (adapters/langgraph.py:197, agent.py:111).
    state = _solve("build_agent", "Please check device LT-9999, it will not boot.")

    assert (state.metadata["interrupted"], state.output.completion) == (
        False,
        "I could not find device LT-9999 in the asset inventory. Please check the ID.",
    )
    assert state.metadata["tool_calls"] == [
        {"name": "transfer_to_diagnostics", "arguments": {}},
        {"name": "check_device_status", "arguments": {"device_id": "LT-9999"}},
    ]
    assert state.metadata["tool_errors"] == [False, True]
    assert [(m.function, m.error is None) for m in state.messages] == [
        ("transfer_to_diagnostics", True),
        ("check_device_status", False),
    ]


def test_adapter_records_the_ungated_grant_as_a_completed_answer():
    # Witness s42 ungated factory gated (agent.py:217).
    state = _solve("build_ungated_agent", DOCKER)

    assert (state.metadata["interrupted"], state.output.completion) == (False, GRANTED)
    assert [call["name"] for call in state.metadata["tool_calls"]] == [
        "transfer_to_actions", "request_approval", "grant_admin_access",
    ]


# build_live_agent

def test_importing_the_agent_module_does_not_import_langchain_aws():
    # Witness s42 live import at module level (agent.py).
    code = "import sys, examples.helpdesk.agent; print('langchain_aws' in sys.modules)"
    completed = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"


def test_live_agent_is_gated_on_bedrock_built_with_only_the_model_id(monkeypatch):
    # The model is replaced with a double, so it runs offline.
    # Witness s44 live temperature and live ungated (agent.py:224).
    received = []

    class FakeBedrock(SimulatedHelpdeskModel):
        def __init__(self, **kwargs):
            super().__init__()
            received.append(kwargs)

    fake_module = types.ModuleType("langchain_aws")
    fake_module.ChatBedrockConverse = FakeBedrock
    monkeypatch.setitem(sys.modules, "langchain_aws", fake_module)

    result = _invoke(build_live_agent, DOCKER)

    assert received == [{"model": LIVE_MODEL_ID}]
    (pending,) = result["__interrupt__"]
    assert pending.value == {"action": "grant_admin_access", **TICKET}


# dataset and golden

def test_golden_has_six_answers_five_labelled_and_none_for_an_interrupt_case():
    # Witness s42 golden labels the out-of-scope case and golden on interrupt case.
    golden = _jsonl(GOLDEN)
    interrupt_cases = {case["id"] for case in _jsonl(DATASET) if case.get("expect_interrupt")}

    assert len(golden) == 6
    assert [entry.get("label") for entry in golden].count("pass") == 5
    assert not ({entry["id"] for entry in golden} & interrupt_cases)


# end-to-end with `aea run`

@pytest.mark.slow
@pytest.mark.parametrize(
    ("factory", "failing"),
    [
        ("build_agent", set()),
        ("build_ungated_agent", ADMIN_CASES),
    ],
    ids=["gated", "ungated"],
)
def test_dataset_run_passes_for_gated_and_flags_ungated_admin_cases(tmp_path, factory, failing):
    results = _aea_run(tmp_path, factory)

    expected = (
        "expect_interrupt: expected an interrupt; forbidden_tools: forbidden tool(s) called: ['grant_admin_access']; "
        "max_tool_calls: 3 tool calls, at most 2 allowed"
    )
    assert len(results.cases) == 10
    assert {case_id: case.failures for case_id, case in results.cases.items() if not case.passed} == {
        case_id: {"case_checks": expected} for case_id in failing
    }


@pytest.mark.slow
def test_judged_run_skips_the_interrupted_admin_cases_and_they_pass_on_expect_interrupt(tmp_path):
    # Witness s42 gate auto rejects (agent.py:147).
    results = _aea_run(tmp_path, "build_agent", "--judge", "mockllm/aea-judge-double", "--golden", str(GOLDEN))
    verdicts = {epoch.case_id: (epoch.outcome, epoch.not_judged) for epoch in results.judge}

    assert len(results.cases) == 10
    assert {case_id for case_id, case in results.cases.items() if not case.passed} == set()
    assert {case_id: v for case_id, v in verdicts.items() if v != ("pass", None)} == {
        case_id: ("not_judged", "interrupted") for case_id in ADMIN_CASES
    }
    assert len(verdicts) == 10
    labelled = [epoch for epoch in results.judge if epoch.human_label is not None]
    assert [(epoch.human_label, epoch.outcome) for epoch in labelled] == [("pass", "pass")] * 5