"""Framework-independent parts of the expense-claim example: the policy, the tools' logic and the model double.

The model is simulated. The double is a deterministic rule engine that reads the system prompt it receives and
applies only the policy rules that prompt states: each rule is one sentence of the prompt (RULE_SENTENCES). So a
prompt edit that drops a sentence drops that rule, which is how the condensed prompt causes a regression offline.
Limits come from the tools (lookup_policy, per_diem); currency conversion always runs through convert_currency.
"""

import json
from dataclasses import dataclass
from typing import Any

RECEIPT_THRESHOLD_USD = 75.0
REFER_ABOVE_USD = 5000.0

# Fixed rates: USD per unit of each currency.
USD_RATES: dict[str, float] = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067}

# Daily meal allowance in USD; cities not listed get the default.
PER_DIEM_USD: dict[str, float] = {"London": 90.0, "Paris": 85.0, "New York": 100.0, "Tokyo": 80.0}
DEFAULT_PER_DIEM_USD = 60.0

CATEGORY_POLICY: dict[str, dict[str, Any]] = {
    "airfare": {"rule": "Economy fares are reimbursed at cost.", "limits": {}},
    "taxi": {"rule": "Taxis are reimbursed at cost.", "limits": {}},
    "lodging": {
        "rule": "Lodging is reimbursed up to a nightly limit; grade 4 and above use the senior limit.",
        "limits": {"nightly_limit_usd": 200.0, "senior_nightly_limit_usd": 300.0, "senior_from_grade": 4},
    },
    "meals": {"rule": "Meals are reimbursed up to the per diem for the trip city.", "limits": {}},
    "alcohol": {"rule": "Alcohol is not reimbursable.", "limits": {}},
}
UNCOVERED_POLICY: dict[str, Any] = {"rule": "Not covered by a category rule; reimbursed at cost.", "limits": {}}

# One prompt sentence per rule. The double applies a rule only if its sentence appears in the system prompt.
RULE_SENTENCES: dict[str, str] = {
    "alcohol": "Alcohol is never reimbursable.",
    "receipt": f"Reject any line over {RECEIPT_THRESHOLD_USD:.0f} USD, after conversion, that has no receipt.",
    "per_diem": "Cap the meal lines at the per diem for the trip city and days.",
    "lodging": "Cap lodging at the nightly limit times the trip days, using the senior limit for senior grades.",
    "refer_total": f"Refer a claim whose total exceeds {REFER_ABOVE_USD:.0f} USD after conversion; do not decide it.",
    "refer_currency": "Refer a claim with a currency that cannot be converted.",
}

_OUTPUT_FORMAT = (
    "Reply with JSON only: decision (approve, reject or refer), claimed_usd, approved_usd, "
    "and one adjustment with a reason for every line you reduce."
)

PROMPT = (
    "You review employee expense claims against the travel policy. "
    "Look up the policy for each category, convert every non-USD line to USD with convert_currency, "
    "and get the per diem for the trip before judging meals. "
    "Apply these rules in order. "
    + " ".join(RULE_SENTENCES.values())
    + " Approve the claim if any amount remains approved, otherwise reject it. "
    + _OUTPUT_FORMAT
)

# A plausible tidy-up: shorter instructions, same rules... except the receipt sentence is gone.
PROMPT_CONDENSED = (
    "You review expense claims. Use the tools for policy, currency and per diem. "
    + " ".join(sentence for rule, sentence in RULE_SENTENCES.items() if rule != "receipt")
    + " Approve if anything remains approved, otherwise reject."
    + _OUTPUT_FORMAT
)

OUT_OF_SCOPE = "I can only review expense claims submitted as JSON."


# Tool logic. Error messages carry no user data, because exception text is kept in traces.
def lookup_policy(category: str) -> str:
    return json.dumps({"category": category, **CATEGORY_POLICY.get(category, UNCOVERED_POLICY)})


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    if from_currency not in USD_RATES or to_currency not in USD_RATES:
        raise ValueError("unsupported currency")
    converted = round(amount * USD_RATES[from_currency] / USD_RATES[to_currency], 2)
    return json.dumps({"amount": converted, "currency": to_currency})


def per_diem(city: str, days: int) -> str:
    daily = PER_DIEM_USD.get(city, DEFAULT_PER_DIEM_USD)
    return json.dumps({"city": city, "days": days, "daily_usd": daily, "total_usd": round(daily * days, 2)})


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


def active_rules(system_prompt: str) -> set[str]:
    return {rule for rule, sentence in RULE_SENTENCES.items() if sentence in system_prompt}


def parse_claim(text: str) -> dict[str, Any] | None:
    try:
        claim = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(claim, dict) or not isinstance(claim.get("lines"), list):
        return None
    return claim


def plan(claim: dict[str, Any], rules: set[str]) -> list[ToolRequest]:
    """Tool calls in order: policy per category, conversion per non-USD line, then per diem if meals are capped."""
    lines = claim["lines"]
    categories = list(dict.fromkeys(line["category"] for line in lines))
    calls = [ToolRequest("lookup_policy", {"category": category}) for category in categories]
    calls += [
        ToolRequest(
            "convert_currency", {"amount": line["amount"], "from_currency": line["currency"], "to_currency": "USD"}
        )
        for line in lines
        if line["currency"] != "USD"
    ]
    if "per_diem" in rules and "meals" in categories:
        trip = claim["trip"]
        calls.append(ToolRequest("per_diem", {"city": trip["city"], "days": trip["days"]}))
    return calls


def next_step(system_prompt: str, claim_text: str, results: list[ToolResult]) -> ToolRequest | str:
    claim = parse_claim(claim_text)
    if claim is None:
        return OUT_OF_SCOPE
    rules = active_rules(system_prompt)
    calls = plan(claim, rules)
    if len(results) < len(calls):
        return calls[len(results)]
    return json.dumps(review(claim, rules, list(zip(calls, results, strict=True))))


def review(claim: dict[str, Any], rules: set[str], steps: list[tuple[ToolRequest, ToolResult]]) -> dict[str, Any]:
    """Apply the active rules to the claim, using only figures the tools returned."""
    policies: dict[str, dict[str, Any]] = {}
    converted: list[float | None] = []  # per non-USD line, in order; None when conversion failed
    allowance: float | None = None
    for request, result in steps:
        if request.name == "lookup_policy":
            policies[request.arguments["category"]] = json.loads(result.output)
        elif request.name == "convert_currency":
            converted.append(json.loads(result.output)["amount"] if result.ok else None)
        elif request.name == "per_diem":
            allowance = json.loads(result.output)["total_usd"]

    conversions = iter(converted)
    amounts: list[float | None] = [
        float(line["amount"]) if line["currency"] == "USD" else next(conversions) for line in claim["lines"]
    ]
    unconvertible = [number for number, usd in enumerate(amounts, start=1) if usd is None]
    if unconvertible and "refer_currency" in rules:
        return {
            "decision": "refer",
            "approved_usd": 0.0,
            "reason": f"line {unconvertible[0]} uses a currency that cannot be converted",
        }
    usd = [amount or 0.0 for amount in amounts]
    claimed = round(sum(usd), 2)
    if claimed > REFER_ABOVE_USD and "refer_total" in rules:
        return {
            "decision": "refer",
            "claimed_usd": claimed,
            "approved_usd": 0.0,
            "reason": "claim total exceeds the referral limit",
        }

    lodging_cap = None
    if "lodging" in rules and "lodging" in policies:
        limits = policies["lodging"]["limits"]
        senior = claim["employee_grade"] >= limits["senior_from_grade"]
        nightly = limits["senior_nightly_limit_usd"] if senior else limits["nightly_limit_usd"]
        lodging_cap = nightly * claim["trip"]["days"]
    remaining: dict[str, float | None] = {"meals": allowance, "lodging": lodging_cap}
    cap_reasons = {"meals": "meals capped at the per diem", "lodging": "lodging capped at the nightly limit"}

    adjustments: list[dict[str, Any]] = []
    approved_total = 0.0
    for number, (line, amount) in enumerate(zip(claim["lines"], usd, strict=True), start=1):
        approved, reason = amount, None
        category = line["category"]
        if category == "alcohol" and "alcohol" in rules:
            approved, reason = 0.0, "alcohol is never reimbursable"
        elif amount > RECEIPT_THRESHOLD_USD and not line["receipt"] and "receipt" in rules:
            approved, reason = 0.0, "no receipt for a line over the receipt threshold"
        elif remaining.get(category) is not None:
            left = remaining[category] or 0.0
            if amount > left:
                approved, reason = round(left, 2), cap_reasons[category]
            remaining[category] = round(left - approved, 2)
        if reason is not None:
            adjustments.append(
                {
                    "line": number,
                    "category": category,
                    "claimed_usd": amount,
                    "approved_usd": approved,
                    "reason": reason,
                }
            )
        approved_total += approved
    approved_total = round(approved_total, 2)
    return {
        "decision": "approve" if approved_total > 0 else "reject",
        "claimed_usd": claimed,
        "approved_usd": approved_total,
        "adjustments": adjustments,
    }
