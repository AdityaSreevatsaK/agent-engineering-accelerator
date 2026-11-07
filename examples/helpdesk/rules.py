"""Framework-independent parts of the IT helpdesk example: the directory, the tools' logic, the prompts and the model
double.

The model is simulated. The double is a deterministic rule engine that reads the system prompt it receives and
applies only the rules that prompt states: each rule is one sentence of a role's prompt (*_SENTENCES). The first
sentence of each prompt names the role, which is how one double plays the supervisor and both workers.

The approval gate is not a rule of the double: it is a node of the actions worker graph that pauses the run with
interrupt() after request_approval. The actions prompt tells the model the workflow pauses there, so the model
calls grant_admin_access as soon as request_approval returns; only the graph stands between the two.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

# Fixed directory. Error messages carry no user data, because exception text is kept in traces.
DEVICES: dict[str, dict[str, Any]] = {
    "LT-1042": {"online": True, "last_seen": "2026-10-22T09:14Z", "os": "Windows 11 24H2", "disk_free_pct": 7},
    "LT-2001": {"online": False, "last_seen": "2026-10-19T17:02Z", "os": "Windows 11 24H2", "disk_free_pct": 41},
    "DT-3300": {"online": True, "last_seen": "2026-10-22T08:55Z", "os": "Ubuntu 24.04", "disk_free_pct": 63},
}
USERS: set[str] = {"asmith", "bchen", "dpatel", "jdoe"}
LOW_DISK_PCT = 10

SUPERVISOR_ROLE = "You are the IT helpdesk supervisor."
DIAGNOSTICS_ROLE = "You are the IT diagnostics specialist."
ACTIONS_ROLE = "You are the IT account actions specialist."

# One prompt sentence per rule. The double applies a rule only if its sentence appears in the system prompt.
SUPERVISOR_SENTENCES: dict[str, str] = {
    "route_diagnostics": (
        "Send questions about a device's health, connectivity or status to diagnostics with transfer_to_diagnostics."
    ),
    "route_actions": "Send password resets and admin access requests to actions with transfer_to_actions.",
    "decline": "Politely decline anything that is not an IT support request, without calling a tool.",
}
DIAGNOSTICS_SENTENCES: dict[str, str] = {
    "check": "Check the device named in the request with check_device_status before answering.",
    "report": "Report whether the device is online, when it was last seen, and any low disk space warning.",
}
ACTIONS_SENTENCES: dict[str, str] = {
    "reset": "Reset a forgotten, expired or locked password with reset_password for the named user.",
    "approval": (
        "For an admin access request, call request_approval first; "
        "the workflow pauses there for the approver and resumes only once access is approved."
    ),
    "grant": "Once request_approval has returned, call grant_admin_access for the same user and device.",
}

SUPERVISOR_PROMPT = (
    SUPERVISOR_ROLE
    + " Read the user's request and hand it to the right team; you do not use any other tools yourself. "
    + " ".join(SUPERVISOR_SENTENCES.values())
)
DIAGNOSTICS_PROMPT = (
    DIAGNOSTICS_ROLE + " " + " ".join(DIAGNOSTICS_SENTENCES.values()) + " Answer in one short paragraph."
)
ACTIONS_PROMPT = (
    ACTIONS_ROLE
    + " "
    + " ".join(ACTIONS_SENTENCES.values())
    + " Never reveal a password. Answer in one short paragraph."
)

OUT_OF_SCOPE = "Sorry, I can only help with IT support requests such as device problems, passwords and access."
NO_DEVICE = "Please tell me the device ID, for example LT-1042, so I can check it."
NO_USER = "Please tell me the user name, for example 'user asmith', so I can action the request."
NOT_APPROVED = "Admin access was not approved, so it has not been granted."

HANDOFF_TEAMS: dict[str, str] = {"transfer_to_diagnostics": "diagnostics", "transfer_to_actions": "actions"}

_DEVICE_ID = re.compile(r"\b([A-Z]{2}-\d{4})\b")
_USER = re.compile(r"\buser\s+([a-z][a-z0-9_-]*)\b", re.IGNORECASE)


# Tool logic.
def check_device_status(device_id: str) -> str:
    if device_id not in DEVICES:
        raise ValueError("unknown device")
    return json.dumps({"device_id": device_id, **DEVICES[device_id]})


def reset_password(username: str) -> str:
    if username not in USERS:
        raise ValueError("unknown user")
    return json.dumps({"username": username, "status": "reset", "delivery": "registered email"})


def request_approval(username: str, device_id: str) -> str:
    if username not in USERS or device_id not in DEVICES:
        raise ValueError("unknown user or device")
    return json.dumps({"ticket": f"APR-{device_id}-{username}", "status": "pending", "approver": "IT security"})


def grant_admin_access(username: str, device_id: str) -> str:
    if username not in USERS or device_id not in DEVICES:
        raise ValueError("unknown user or device")
    return json.dumps({"username": username, "device_id": device_id, "admin": True})


# The model double.
@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    output: str


def classify(request: str) -> str | None:
    """The kind of IT request: admin, password or device; None when it is not an IT request."""
    text = request.lower()
    if "admin" in text:
        return "admin"
    if "password" in text or "locked out" in text:
        return "password"
    if _DEVICE_ID.search(request) or any(word in text for word in ("laptop", "desktop", "device", "wi-fi", "vpn")):
        return "device"
    return None


def _device(request: str) -> str | None:
    match = _DEVICE_ID.search(request)
    return match.group(1) if match else None


def _user(request: str) -> str | None:
    match = _USER.search(request)
    return match.group(1).lower() if match else None


def _active(system_prompt: str, sentences: dict[str, str]) -> set[str]:
    return {rule for rule, sentence in sentences.items() if sentence in system_prompt}


def role_of(system_prompt: str) -> str:
    """Supervisor, diagnostics or actions, from the role sentence the prompt opens with."""
    for role, sentence in (
        ("supervisor", SUPERVISOR_ROLE),
        ("diagnostics", DIAGNOSTICS_ROLE),
        ("actions", ACTIONS_ROLE),
    ):
        if system_prompt.startswith(sentence):
            return role
    raise ValueError("system prompt names no helpdesk role")


def next_step(system_prompt: str, request: str, results: list[ToolResult]) -> ToolRequest | str:
    role = role_of(system_prompt)
    if role == "supervisor":
        return _supervisor(_active(system_prompt, SUPERVISOR_SENTENCES), request)
    if role == "diagnostics":
        return _diagnostics(_active(system_prompt, DIAGNOSTICS_SENTENCES), request, results)
    return _actions(_active(system_prompt, ACTIONS_SENTENCES), request, results)


def _supervisor(rules: set[str], request: str) -> ToolRequest | str:
    kind = classify(request)
    if kind == "device" and "route_diagnostics" in rules:
        return ToolRequest("transfer_to_diagnostics", {})
    if kind in ("password", "admin") and "route_actions" in rules:
        return ToolRequest("transfer_to_actions", {})
    return OUT_OF_SCOPE


def _diagnostics(rules: set[str], request: str, results: list[ToolResult]) -> ToolRequest | str:
    device_id = _device(request)
    if device_id is None:
        return NO_DEVICE
    if "check" in rules and not results:
        return ToolRequest("check_device_status", {"device_id": device_id})
    if not results:
        return f"I have not checked {device_id}."
    result = results[-1]
    if not result.ok:
        return f"I could not find device {device_id} in the asset inventory. Please check the ID."
    status = json.loads(result.output)
    if "report" not in rules:
        return f"I checked {device_id}."
    state = "online" if status["online"] else "offline"
    reply = f"{device_id} is {state}, last seen {status['last_seen']}, running {status['os']}."
    if status["disk_free_pct"] < LOW_DISK_PCT:
        reply += f" Warning: low disk space, only {status['disk_free_pct']}% free, which can slow it down."
    return reply


def _actions(rules: set[str], request: str, results: list[ToolResult]) -> ToolRequest | str:
    username = _user(request)
    if username is None:
        return NO_USER
    done = {result.name: result for result in results}
    if classify(request) == "password":
        if "reset" not in rules:
            return "I cannot reset passwords."
        if "reset_password" not in done:
            return ToolRequest("reset_password", {"username": username})
        if not done["reset_password"].ok:
            return f"I could not find user {username} in the directory, so no password was reset."
        return f"The password for {username} has been reset; a temporary password was sent to their registered email."

    device_id = _device(request)
    if device_id is None:
        return NO_DEVICE
    arguments = {"username": username, "device_id": device_id}
    if "approval" in rules and "request_approval" not in done:
        return ToolRequest("request_approval", arguments)
    if "request_approval" in done and not done["request_approval"].ok:
        return f"I could not raise an approval for {username} on {device_id}, so no access was granted."
    if "grant" not in rules:
        if "request_approval" in done:
            return f"An approval request for {username} on {device_id} has been raised."
        return "I cannot grant admin access."
    if "grant_admin_access" not in done:
        return ToolRequest("grant_admin_access", arguments)
    if not done["grant_admin_access"].ok:
        return f"Granting admin access to {username} on {device_id} failed."
    return f"Admin access on {device_id} has been granted to {username}."
