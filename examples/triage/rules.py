"""Framework-independent parts of the ticket-triage example: the data, the tools' logic and the classifier double.

The classifier is simulated. The double is a deterministic rule engine that reads the classifier prompt it receives
and applies only the routing rules that prompt states: each rule is one sentence of the prompt (RULES), tried in the
order the sentences appear in the prompt, first match wins. So a prompt edit that drops or reorders a sentence changes
the routing, which is how the reworded prompt causes a regression offline. Matching is by phrases in the ticket text.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

CATEGORIES = ("billing", "technical", "account", "other")
PRIORITIES = ("high", "normal", "low")

INVOICES: dict[str, dict[str, Any]] = {
    "INV-1001": {"amount_usd": 49.0, "status": "paid", "date": "2026-09-01"},
    "INV-1002": {"amount_usd": 49.0, "status": "refunded", "date": "2026-09-15"},
    "INV-1003": {"amount_usd": 99.0, "status": "overdue", "date": "2026-10-01"},
}

# Known issues, matched when any keyword appears in the query.
KNOWN_ISSUES: list[dict[str, Any]] = [
    {
        "id": "KI-42",
        "keywords": ["csv export"],
        "title": "CSV export fails for reports over 10,000 rows",
        "workaround": "Filter the report below 10,000 rows or export it as XLSX.",
    },
    {
        "id": "KI-57",
        "keywords": ["sso"],
        "title": "SSO sign-in loops back to the login page on Safari",
        "workaround": "Clear the site cookies or sign in from another browser.",
    },
    {
        "id": "KI-63",
        "keywords": ["outage"],
        "title": "Dashboard outage in the EU region",
        "workaround": "Engineers are restoring service; follow the status page for updates.",
    },
]


@dataclass(frozen=True)
class Rule:
    """A routing rule: the prompt sentence that states it, and what it does when one of its triggers matches.

    A trigger is a tuple of phrases that must all appear in the lower-cased ticket text.
    """

    sentence: str
    triggers: tuple[tuple[str, ...], ...]
    category: str
    priority: str


_BILLING_WORDS = ("invoice", "refund", "payment", "charge", "billed")
_ANGER_WORDS = ("angry", "furious")

URGENT_BILLING = Rule(
    "A billing ticket that reports a duplicate charge, or comes from an angry customer, is high priority "
    "and must be escalated to a human.",
    (("charged twice",), ("double charged",), ("duplicate charge",))
    + tuple((billing, anger) for billing in _BILLING_WORDS for anger in _ANGER_WORDS),
    "billing",
    "high",
)
OUTAGE = Rule(
    "A technical ticket that reports an outage is high priority.",
    (("outage",),),
    "technical",
    "high",
)
BILLING = Rule(
    "Tickets about invoices, refunds, payments or charges are billing, normal priority.",
    tuple((word,) for word in _BILLING_WORDS),
    "billing",
    "normal",
)
TECHNICAL = Rule(
    "Tickets about errors, crashes, bugs, slowness or login problems are technical, normal priority.",
    (("error",), ("crash",), ("bug",), ("slow",), ("login",)),
    "technical",
    "normal",
)
# The reworded prompt's technical sentence: it adds "something that happened twice", meant for repeated failures.
TECHNICAL_REWORDED = Rule(
    "Technical, normal priority: errors, crashes, bugs, slowness, login problems, or something that happened twice.",
    (("error",), ("crash",), ("bug",), ("slow",), ("login",), ("twice",)),
    "technical",
    "normal",
)
ACCOUNT = Rule(
    "Tickets about passwords, profile details or closing an account are account, normal priority.",
    (("password",), ("profile",), ("close my account",)),
    "account",
    "normal",
)

RULES: tuple[Rule, ...] = (URGENT_BILLING, OUTAGE, BILLING, TECHNICAL, TECHNICAL_REWORDED, ACCOUNT)

FALLBACK_SENTENCE = "Anything else is other, low priority."

_OUTPUT_FORMAT = 'Reply with JSON only, for example {"category": "billing", "priority": "normal"}.'

PROMPT = (
    "You triage customer support tickets for a software subscription service. "
    "Give each ticket exactly one category (billing, technical, account or other) "
    "and a priority (high, normal or low). "
    "Use the first rule that matches. "
    + " ".join(rule.sentence for rule in (URGENT_BILLING, OUTAGE, BILLING, TECHNICAL, ACCOUNT))
    + f" {FALLBACK_SENTENCE} "
    + _OUTPUT_FORMAT
)

# A plausible tidy-up: technical listed first and broadened to cover repeated failures, billing kept, and the
# urgent-billing sentence folded away. A duplicate charge now reads as "something that happened twice".
PROMPT_REWORDED = (
    "You triage support tickets. Pick one category (technical, billing, account or other) and a priority. "
    "Use the first rule that matches. "
    + " ".join(rule.sentence for rule in (OUTAGE, TECHNICAL_REWORDED, BILLING, ACCOUNT))
    + f" {FALLBACK_SENTENCE} "
    + _OUTPUT_FORMAT
)


# Tool logic. Error text carries no user data.
def lookup_invoice(invoice_id: str) -> str:
    invoice = INVOICES.get(invoice_id)
    if invoice is None:
        return json.dumps({"invoice_id": invoice_id, "found": False})
    return json.dumps({"invoice_id": invoice_id, "found": True, **invoice})


def search_known_issues(query: str) -> str:
    text = query.lower()
    matches = [issue for issue in KNOWN_ISSUES if any(keyword in text for keyword in issue["keywords"])]
    return json.dumps(
        [{key: issue[key] for key in ("id", "title", "workaround")} for issue in sorted(matches, key=lambda i: i["id"])]
    )


def escalate_to_human(queue: str, priority: str, summary: str) -> str:
    reference = "ESC-" + hashlib.sha256(f"{queue}|{priority}|{summary}".encode()).hexdigest()[:6].upper()
    return json.dumps({"escalation_id": reference, "queue": queue, "priority": priority})


# The classifier double.
def active_rules(prompt: str) -> list[Rule]:
    """The rules the prompt states, in the order it states them."""
    return sorted((rule for rule in RULES if rule.sentence in prompt), key=lambda rule: prompt.index(rule.sentence))


def classify(prompt: str, ticket: str) -> dict[str, str]:
    text = ticket.lower()
    for rule in active_rules(prompt):
        if any(all(phrase in text for phrase in trigger) for trigger in rule.triggers):
            return {"category": rule.category, "priority": rule.priority}
    return {"category": "other", "priority": "low" if FALLBACK_SENTENCE in prompt else "normal"}
