import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT
from inspect_ai.solver import TaskState
from langchain_core.messages import HumanMessage

from agent_accelerator.compare import load_results
from agent_accelerator.dataset import load_dataset
from agent_accelerator.judge import load_golden

REPO = Path(__file__).resolve().parents[2]
# The examples are imported from the repo root, as `aea` does when it loads --agent and --scorer.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from examples.expense.agent import build_agent, build_condensed_agent  # noqa: E402
from examples.expense.rules import (  # noqa: E402
    OUT_OF_SCOPE,
    PROMPT,
    PROMPT_CONDENSED,
    RULE_SENTENCES,
    ToolRequest,
    ToolResult,
    active_rules,
    convert_currency,
    lookup_policy,
    next_step,
    per_diem,
    plan,
    review,
)
from examples.expense.scorers import amounts_grounded, ungrounded  # noqa: E402

DATASET = REPO / "examples" / "expense" / "dataset.jsonl"
GOLDEN = REPO / "examples" / "expense" / "golden.jsonl"
ALL_RULES = {"alcohol", "receipt", "per_diem", "lodging", "refer_total", "refer_currency"}
TOOLS = {"lookup_policy": lookup_policy, "convert_currency": convert_currency, "per_diem": per_diem}


def _line(category, amount, currency="USD", receipt=True):
    return {"category": category, "amount": amount, "currency": currency, "date": "2026-09-08", "receipt": receipt}


def _claim(*lines, city="Chicago", days=1, grade=2):
    return {"employee_grade": grade, "trip": {"city": city, "days": days}, "lines": list(lines)}


def _execute(call):
    """Runs a planned call through the real tool, turning a tool error into a failed result as ToolNode does."""
    try:
        return ToolResult(call.name, True, TOOLS[call.name](**call.arguments))
    except ValueError as exc:
        return ToolResult(call.name, False, f"Error: {exc}")


def _review(claim, rules=frozenset(ALL_RULES)):
    calls = plan(claim, set(rules))
    return review(claim, set(rules), [(call, _execute(call)) for call in calls])


def _adjustment(line, category, claimed, approved, reason):
    return {"line": line, "category": category, "claimed_usd": claimed, "approved_usd": approved, "reason": reason}


NO_RECEIPT = "no receipt for a line over the receipt threshold"
ALCOHOL = "alcohol is never reimbursable"


# active_rules


def test_full_prompt_activates_every_rule_and_condensed_prompt_lacks_only_the_receipt_rule():
    # Witness s17 condensed drops alcohol: `if rule != "receipt"` -> `if rule != "alcohol"` in PROMPT_CONDENSED
    # (rules.py:63). Witness s17 prompt drops first sentence: join `list(RULE_SENTENCES.values())[1:]` in PROMPT
    # (rules.py:55).
    assert active_rules(PROMPT) == ALL_RULES
    assert active_rules(PROMPT_CONDENSED) == ALL_RULES - {"receipt"}


@pytest.mark.parametrize("rule", sorted(ALL_RULES))
def test_each_rule_sentence_on_its_own_activates_exactly_that_rule(rule):
    # Witness s17 sentence prefix match: `sentence in system_prompt` -> `sentence[:10] in system_prompt`
    # (rules.py:103); "Refer a cl" is shared by both referral rules, so each activates the other.
    assert active_rules(RULE_SENTENCES[rule]) == {rule}


def test_prompt_without_rule_sentences_activates_no_rule():
    # Witness s17 sentence prefix match (as above): "Refer a cl" then matches inside this prompt.
    assert active_rules("Refer a claim to a manager. Review it.") == set()


# plan


def test_plan_looks_up_each_category_once_then_converts_non_usd_lines_then_gets_the_per_diem():
    # Witness s17 plan categories not deduplicated: drop `dict.fromkeys` (rules.py:119).
    # Witness s17 plan converts usd lines: `if line["currency"] != "USD"` -> `if True` (rules.py:126).
    claim = _claim(
        _line("meals", 30.0),
        _line("taxi", 20.0, "EUR"),
        _line("meals", 4000.0, "JPY"),
        _line("lodging", 150.0),
        _line("alcohol", 10.0, "GBP"),
        city="London",
        days=3,
    )

    assert plan(claim, ALL_RULES) == [
        ToolRequest("lookup_policy", {"category": "meals"}),
        ToolRequest("lookup_policy", {"category": "taxi"}),
        ToolRequest("lookup_policy", {"category": "lodging"}),
        ToolRequest("lookup_policy", {"category": "alcohol"}),
        ToolRequest("convert_currency", {"amount": 20.0, "from_currency": "EUR", "to_currency": "USD"}),
        ToolRequest("convert_currency", {"amount": 4000.0, "from_currency": "JPY", "to_currency": "USD"}),
        ToolRequest("convert_currency", {"amount": 10.0, "from_currency": "GBP", "to_currency": "USD"}),
        ToolRequest("per_diem", {"city": "London", "days": 3}),
    ]


@pytest.mark.parametrize(
    ("lines", "rules"),
    [
        ([_line("meals", 30.0)], ALL_RULES - {"per_diem"}),
        ([_line("taxi", 30.0)], ALL_RULES),
    ],
    ids=["per_diem_rule_inactive", "no_meals_line"],
)
def test_plan_requests_no_per_diem_unless_the_rule_is_active_and_meals_are_claimed(lines, rules):
    # Witness s17 per diem ignores rule: `if "per_diem" in rules and "meals" in categories` ->
    # `if "meals" in categories` (rules.py:128). Witness s17 per diem ignores meals: -> `if "per_diem" in rules`.
    calls = plan(_claim(*lines), rules)

    assert [call.name for call in calls] == ["lookup_policy"]


# review: receipt rule


@pytest.mark.parametrize(
    ("amount", "currency", "receipt", "claimed", "approved"),
    [
        (120.0, "USD", False, 120.0, 0.0),
        (75.0, "USD", False, 75.0, 75.0),
        (75.01, "USD", False, 75.01, 0.0),
        (70.0, "EUR", False, 75.6, 0.0),  # 70 x 1.08 = 75.60, over only after conversion
        (10000.0, "JPY", False, 67.0, 67.0),  # 10,000 x 0.0067 = 67.00, over only before conversion
        (120.0, "USD", True, 120.0, 120.0),
    ],
    ids=["usd_over", "usd_75_boundary_kept", "usd_just_over", "eur_over_after_conversion", "jpy_under", "receipt"],
)
def test_line_over_75_usd_after_conversion_without_receipt_is_rejected(amount, currency, receipt, claimed, approved):
    # Witness s17 receipt boundary: `amount > RECEIPT_THRESHOLD_USD` -> `amount >= RECEIPT_THRESHOLD_USD`
    # (rules.py:195). Witness s17 receipt before conversion: `amount >` -> `float(line["amount"]) >`.
    # Witness s17 receipt ignores receipt flag: drop `and not line["receipt"]`.
    result = _review(_claim(_line("taxi", amount, currency, receipt)))

    rejected = [_adjustment(1, "taxi", claimed, 0.0, NO_RECEIPT)] if approved == 0.0 else []
    assert result == {
        "decision": "reject" if approved == 0.0 else "approve",
        "claimed_usd": claimed,
        "approved_usd": approved,
        "adjustments": rejected,
    }


def test_line_over_75_usd_without_receipt_is_paid_when_the_receipt_rule_is_inactive():
    # Witness s17 receipt ignores rule: drop `and "receipt" in rules` (rules.py:195).
    result = _review(_claim(_line("taxi", 120.0, receipt=False)), ALL_RULES - {"receipt"})

    assert result == {"decision": "approve", "claimed_usd": 120.0, "approved_usd": 120.0, "adjustments": []}


# review: alcohol rule


@pytest.mark.parametrize("receipt", [True, False], ids=["with_receipt", "without_receipt"])
def test_alcohol_is_never_reimbursed_and_takes_precedence_over_the_receipt_rule(receipt):
    # Witness s17 alcohol ignored: `if category == "alcohol" and "alcohol" in rules:` -> `if False:` (rules.py:193).
    # Witness s17 receipt before alcohol: swap the alcohol and receipt branches (rules.py:193-196); the 120 USD
    # line without a receipt then carries the receipt reason.
    result = _review(_claim(_line("alcohol", 120.0, receipt=receipt)))

    assert result == {
        "decision": "reject",
        "claimed_usd": 120.0,
        "approved_usd": 0.0,
        "adjustments": [_adjustment(1, "alcohol", 120.0, 0.0, ALCOHOL)],
    }


def test_alcohol_is_paid_when_the_alcohol_rule_is_inactive():
    # Witness s17 alcohol ignores rule: drop `and "alcohol" in rules` (rules.py:193).
    result = _review(_claim(_line("alcohol", 60.0)), ALL_RULES - {"alcohol"})

    assert result == {"decision": "approve", "claimed_usd": 60.0, "approved_usd": 60.0, "adjustments": []}


# review: per diem rule


def test_meals_are_capped_at_the_per_diem_in_line_order_until_the_allowance_is_exhausted():
    # London per diem 90 x 2 days = 180: 100 and 50 paid (30 left), 60 capped to 30, then 20 gets nothing.
    # Witness s17 cap not consumed: `remaining[category] = round(left - approved, 2)` -> `= left` (rules.py:201).
    # Witness s17 cap pays nothing: `approved, reason = round(left, 2), cap_reasons` -> `= 0.0, cap_reasons`.
    result = _review(
        _claim(
            _line("meals", 100.0),
            _line("meals", 50.0),
            _line("meals", 60.0),
            _line("meals", 20.0),
            city="London",
            days=2,
        )
    )

    capped = "meals capped at the per diem"
    assert result == {
        "decision": "approve",
        "claimed_usd": 230.0,
        "approved_usd": 180.0,
        "adjustments": [_adjustment(3, "meals", 60.0, 30.0, capped), _adjustment(4, "meals", 20.0, 0.0, capped)],
    }


def test_meals_are_not_capped_when_the_per_diem_rule_is_inactive():
    # Witness s17 per diem ignores rule (as for plan): the per diem is fetched and caps the meals.
    result = _review(_claim(_line("meals", 100.0), _line("meals", 120.0), city="London"), ALL_RULES - {"per_diem"})

    assert result == {"decision": "approve", "claimed_usd": 220.0, "approved_usd": 220.0, "adjustments": []}


def test_meal_rejected_for_no_receipt_does_not_use_up_the_per_diem():
    # London 1 day = 90. Receipt first: line 1 rejected, line 2 (50) paid. Cap first would pay 90 then 0.
    # Witness s17 cap before receipt: swap the receipt and cap branches (rules.py:195-201).
    result = _review(_claim(_line("meals", 120.0, receipt=False), _line("meals", 50.0), city="London"))

    assert result == {
        "decision": "approve",
        "claimed_usd": 170.0,
        "approved_usd": 50.0,
        "adjustments": [_adjustment(1, "meals", 120.0, 0.0, NO_RECEIPT)],
    }


# review: lodging rule


@pytest.mark.parametrize(("grade", "approved"), [(3, 400.0), (4, 600.0)], ids=["grade_3_standard", "grade_4_senior"])
def test_lodging_is_capped_at_the_nightly_limit_times_days_with_the_senior_limit_from_grade_4(grade, approved):
    # 2 nights: standard 200 x 2 = 400, senior 300 x 2 = 600; 650 claimed.
    # Witness s17 senior boundary: `>= limits["senior_from_grade"]` -> `> limits["senior_from_grade"]` (rules.py:182).
    # Witness s17 lodging cap ignores days: `nightly * claim["trip"]["days"]` -> `nightly` (rules.py:184).
    result = _review(_claim(_line("lodging", 650.0), days=2, grade=grade))

    assert result == {
        "decision": "approve",
        "claimed_usd": 650.0,
        "approved_usd": approved,
        "adjustments": [_adjustment(1, "lodging", 650.0, approved, "lodging capped at the nightly limit")],
    }


# review: referrals


@pytest.mark.parametrize(
    ("line", "claimed"),
    [(_line("airfare", 5000.01), 5000.01), (_line("airfare", 4700.0, "EUR"), 5076.0)],
    ids=["usd_just_over", "eur_over_after_conversion"],
)
def test_claim_over_5000_usd_after_conversion_is_referred_without_a_decision(line, claimed):
    # Witness s17 refer total ignored: `if claimed > REFER_ABOVE_USD and "refer_total" in rules:` -> `if False:`
    # (rules.py:171).
    assert _review(_claim(line)) == {
        "decision": "refer",
        "claimed_usd": claimed,
        "approved_usd": 0.0,
        "reason": "claim total exceeds the referral limit",
    }


@pytest.mark.parametrize(
    ("amount", "rules"),
    [(5000.0, ALL_RULES), (5000.01, ALL_RULES - {"refer_total"})],
    ids=["exactly_5000", "refer_total_rule_inactive"],
)
def test_claim_at_5000_usd_or_with_the_refer_rule_inactive_is_decided(amount, rules):
    # Witness s17 refer boundary: `claimed > REFER_ABOVE_USD` -> `claimed >= REFER_ABOVE_USD` (rules.py:171).
    # Witness s17 refer total ignores rule: drop `and "refer_total" in rules`.
    result = _review(_claim(_line("airfare", amount)), rules)

    assert result == {"decision": "approve", "claimed_usd": amount, "approved_usd": amount, "adjustments": []}


@pytest.mark.parametrize("airfare", [100.0, 6000.0], ids=["small_claim", "over_limit_claim"])
def test_claim_with_an_unconvertible_currency_is_referred_naming_the_first_such_line(airfare):
    # The CHF line fails in convert_currency. Currency referral comes before the total referral.
    # Witness s17 currency line 0-based: `enumerate(amounts, start=1)` -> `start=0` (rules.py:162).
    # Witness s17 total before currency: guard the currency check with `and sum(a or 0.0 for a in amounts) <=
    # REFER_ABOVE_USD` (rules.py:163), so an over-limit claim takes the total referral.
    result = _review(_claim(_line("airfare", airfare), _line("taxi", 30.0, "CHF"), _line("taxi", 40.0, "CHF")))

    assert result == {
        "decision": "refer",
        "approved_usd": 0.0,
        "reason": "line 2 uses a currency that cannot be converted",
    }


def test_unconvertible_line_counts_as_zero_when_the_currency_referral_rule_is_inactive():
    # Witness s17 currency referral ignores rule: drop `and "refer_currency" in rules` (rules.py:163).
    result = _review(_claim(_line("taxi", 40.0), _line("taxi", 30.0, "CHF")), ALL_RULES - {"refer_currency"})

    assert result == {"decision": "approve", "claimed_usd": 40.0, "approved_usd": 40.0, "adjustments": []}


# tools


@pytest.mark.parametrize(
    ("amount", "source", "target", "converted"),
    [
        (100.0, "EUR", "USD", 108.0),
        (10.0, "GBP", "USD", 12.7),
        (10000.0, "JPY", "USD", 67.0),
        (100.0, "USD", "EUR", 92.59),  # 100 / 1.08 = 92.592...
        (50.0, "USD", "USD", 50.0),
    ],
    ids=["eur", "gbp", "jpy", "usd_to_eur", "usd"],
)
def test_convert_currency_uses_the_fixed_usd_rates_rounded_to_cents(amount, source, target, converted):
    # Witness s17 convert multiplies by target rate: `/ USD_RATES[to_currency]` -> `* USD_RATES[to_currency]`
    # (rules.py:79). Witness s17 eur rate: `"EUR": 1.08` -> `"EUR": 1.1` (rules.py:17).
    assert json.loads(convert_currency(amount, source, target)) == {"amount": converted, "currency": target}


@pytest.mark.parametrize(("source", "target"), [("CHF", "USD"), ("USD", "CHF")], ids=["from", "to"])
def test_convert_currency_rejects_an_unsupported_currency_without_echoing_it(source, target):
    # Witness s17 convert target unchecked: drop `or to_currency not in USD_RATES` (rules.py:77); a KeyError then
    # escapes instead of ValueError.
    with pytest.raises(ValueError, match="^unsupported currency$"):
        convert_currency(10.0, source, target)


@pytest.mark.parametrize(
    ("city", "days", "daily", "total"),
    [
        ("London", 3, 90.0, 270.0),
        ("Paris", 2, 85.0, 170.0),
        ("New York", 1, 100.0, 100.0),
        ("Tokyo", 2, 80.0, 160.0),
        ("Chicago", 2, 60.0, 120.0),
    ],
    ids=["london", "paris", "new_york", "tokyo", "unlisted_city_default"],
)
def test_per_diem_is_the_city_daily_allowance_times_days(city, days, daily, total):
    # Witness s17 per diem default: `DEFAULT_PER_DIEM_USD = 60.0` -> `= 50.0` (rules.py:21).
    # Witness s17 per diem total ignores days: `round(daily * days, 2)` -> `round(daily, 2)` (rules.py:85).
    assert json.loads(per_diem(city, days)) == {"city": city, "days": days, "daily_usd": daily, "total_usd": total}


def test_lookup_policy_returns_the_lodging_limits_and_a_generic_rule_for_an_unknown_category():
    # Witness s17 unknown category gets taxi policy: `.get(category, UNCOVERED_POLICY)` ->
    # `.get(category, CATEGORY_POLICY["taxi"])` (rules.py:73).
    lodging = json.loads(lookup_policy("lodging"))
    unknown = json.loads(lookup_policy("gifts"))

    assert lodging["limits"] == {"nightly_limit_usd": 200.0, "senior_nightly_limit_usd": 300.0, "senior_from_grade": 4}
    assert unknown == {"category": "gifts", "rule": "Not covered by a category rule; reimbursed at cost.", "limits": {}}


# next_step and the agent


@pytest.mark.parametrize(
    "text",
    ["what is the per diem in London?", '["lines"]', '{"lines": "taxi"}'],
    ids=["prose", "array", "lines_not_list"],
)
def test_input_that_is_not_a_json_claim_with_lines_gets_the_out_of_scope_reply(text):
    # Witness s17 parse accepts any lines: drop `or not isinstance(claim.get("lines"), list)` (rules.py:111).
    assert next_step(PROMPT, text, []) == OUT_OF_SCOPE


def test_agent_reply_is_the_review_of_the_claim_and_a_tool_error_becomes_a_currency_referral():
    # Witness s17 agent tool errors ok: `ok = message.status != "error"` -> `ok = True` (agent.py:63); the error text
    # is then parsed as a conversion result.
    clean = _claim(_line("taxi", 80.0, "EUR", receipt=False), _line("meals", 120.0), city="Paris", days=1)
    unsupported = _claim(_line("taxi", 40.0), _line("taxi", 30.0, "CHF"))

    replies = [
        json.loads(build_agent().invoke({"messages": [HumanMessage(json.dumps(claim))]})["messages"][-1].content)
        for claim in (clean, unsupported)
    ]

    assert replies[0] == {
        "decision": "approve",
        "claimed_usd": 206.4,
        "approved_usd": 85.0,
        "adjustments": [
            _adjustment(1, "taxi", 86.4, 0.0, NO_RECEIPT),
            _adjustment(2, "meals", 120.0, 85.0, "meals capped at the per diem"),
        ],
    }
    assert replies[1] == {
        "decision": "refer",
        "approved_usd": 0.0,
        "reason": "line 2 uses a currency that cannot be converted",
    }


# scorers: ungrounded

CLAIM = _claim(_line("taxi", 100.0, "EUR"), _line("meals", 50.0))  # 108.00 + 50.00 = 158.00 USD
UNCONVERTIBLE = _claim(_line("taxi", 100.0, "CHF"), _line("meals", 50.0))


def _reply(claimed=158.0, approved=158.0, adjustments=(), decision="approve"):
    return {"decision": decision, "claimed_usd": claimed, "approved_usd": approved, "adjustments": list(adjustments)}


def _adj(line=1, claimed=108.0, approved=0.0):
    return {"line": line, "claimed_usd": claimed, "approved_usd": approved, "reason": "x"}


@pytest.mark.parametrize("prompt", [PROMPT, PROMPT_CONDENSED], ids=["full", "condensed"])
def test_every_dataset_reply_from_the_rule_engine_is_grounded(prompt):
    # Control: the scorer accepts genuine output from both prompts, including referrals and adjustments.
    # Witness s17 grounded tolerance negative: `TOLERANCE = 0.005` -> `TOLERANCE = -1.0` (scorers.py:23).
    claims = [json.loads(json.loads(line)["input"]) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    rules = active_rules(prompt)
    problems = {i: ungrounded(claim, _review(claim, rules)) for i, claim in enumerate(claims)}

    assert len(claims) == 12
    assert {i: p for i, p in problems.items() if p is not None} == {}


@pytest.mark.parametrize(
    ("claim", "reply", "problem"),
    [
        (CLAIM, _reply(adjustments=[_adj(2, 50.0, 50.0)]), None),
        (CLAIM, _reply(approved=158.004), None),
        (CLAIM, _reply(approved=50.0, adjustments=[_adj(1, 108.0, 0.0)]), None),
        (CLAIM, _reply(decision="refer", approved=0.0), None),
        (UNCONVERTIBLE, {"decision": "refer", "approved_usd": 0.0, "reason": "x"}, None),
        (CLAIM, _reply(decision="refer", approved=158.0), "a referral approves nothing"),
        (CLAIM, {"decision": "refer", "reason": "x"}, "a referral approves nothing"),
        (
            CLAIM,
            _reply(decision="refer", claimed=150.0, approved=0.0),
            "claimed_usd is not the converted sum of the lines",
        ),
        (
            UNCONVERTIBLE,
            _reply(claimed=50.0, approved=50.0),
            "claimed_usd given for a claim with an unconvertible line",
        ),
        (CLAIM, _reply(claimed=150.0, approved=150.0), "claimed_usd is not the converted sum of the lines"),
        (CLAIM, _reply(claimed=158.01), "claimed_usd is not the converted sum of the lines"),
        (
            _claim(_line("taxi", 1.0)),
            _reply(claimed=True, approved=True),
            "claimed_usd is not the converted sum of the lines",
        ),
        (CLAIM, _reply(adjustments=[_adj(0)]), "adjustment for unknown line 0"),
        (CLAIM, _reply(adjustments=[_adj(3)]), "adjustment for unknown line 3"),
        (CLAIM, _reply(adjustments=[_adj("1")]), "adjustment for unknown line 1"),
        (CLAIM, _reply(adjustments=[_adj(1, 100.0, 0.0)]), "line 1 claimed_usd is not its converted amount"),
        (CLAIM, _reply(adjustments=[_adj(1, 108.0, 108.02)]), "line 1 approved_usd is outside 0..claimed"),
        (CLAIM, _reply(adjustments=[_adj(1, 108.0, -1.0)]), "line 1 approved_usd is outside 0..claimed"),
        (CLAIM, _reply(adjustments=[_adj(1, 108.0, "0")]), "line 1 approved_usd is outside 0..claimed"),
        (
            CLAIM,
            _reply(approved=158.0, adjustments=[_adj(1, 108.0, 0.0)]),
            "approved_usd is not the sum of the approved lines",
        ),
        (CLAIM, {"decision": "approve", "claimed_usd": 158.0}, "approved_usd is not the sum of the approved lines"),
        (
            UNCONVERTIBLE,
            {"decision": "approve", "approved_usd": 50.0, "adjustments": [_adj(2, 50.0, 50.0)]},
            "approved_usd given for a claim with an unconvertible line",
        ),
        (
            UNCONVERTIBLE,
            {"decision": "approve", "approved_usd": 0.0, "adjustments": [_adj(1, 0.0, 0.0)]},
            "adjustment for unknown line 1",
        ),
    ],
    ids=[
        "grounded_adjustment_at_full_amount",
        "grounded_within_half_a_cent",
        "grounded_line_rejected",
        "grounded_referral_with_claimed",
        "grounded_referral_unconvertible",
        "referral_approves_something",
        "referral_without_approved",
        "referral_claimed_wrong",
        "claimed_for_unconvertible",
        "claimed_unconverted_sum",
        "claimed_one_cent_off",
        "claimed_bool",
        "adjustment_line_zero",
        "adjustment_line_past_end",
        "adjustment_line_not_int",
        "adjustment_claimed_unconverted",
        "adjustment_approved_over_claimed",
        "adjustment_approved_negative",
        "adjustment_approved_not_number",
        "approved_not_sum",
        "approved_missing",
        "approved_for_unconvertible",
        "adjustment_for_unconvertible_line",
    ],
)
def test_ungrounded_names_the_first_amount_not_traceable_to_the_claim(claim, reply, problem):
    # Witnesses, all scorers.py: s17 grounded referral approves (drop the referral approval check, :40-41);
    # s17 grounded referral not short-circuited (drop `if reply.get("decision") == "refer": return None`, :47-48);
    # s17 grounded unconvertible claimed (drop the `None in usd` check, :43-44); s17 grounded bool accepted (drop
    # `and not isinstance(a, bool)`, :32); s17 grounded line upper bound (`<= len(usd)` -> `<= len(usd) + 1`, :53);
    # s17 grounded adjustment claimed (`if not _same(adjustment.get("claimed_usd"), line_usd):` -> `if False`, :56);
    # s17 grounded approved upper bound (drop `<= line_usd + TOLERANCE`, :59); s17 grounded approved sum
    # (`if not _same(approved, ...)` -> `if False`, :64); s17 grounded tolerance zero (`TOLERANCE = 0.005` -> `0.0`);
    # s17 grounded claimed sum (`if not _same(reply["claimed_usd"], ...)` -> `if False`, :45); s17 grounded
    # unconvertible approved (`if None in approved_by_line:` -> `if False`, :62); s17 grounded unconvertible adjustment
    # line (drop `or usd[number - 1] is None`, :53); s17 grounded no conversion (`line["amount"] * rate` ->
    # `line["amount"]`, :28).
    assert ungrounded(claim, reply) == problem


def test_adjustment_approved_usd_given_as_a_bool_is_not_grounded():
    # Witness: drop `isinstance(line_approved, bool) or` from the approved_usd check; True passes as 1.0.
    reply = _reply(approved=51.0, adjustments=[_adj(1, 108.0, True)])

    assert ungrounded(CLAIM, reply) == "line 1 approved_usd is outside 0..claimed"


# scorers: amounts_grounded


def _score(claim_text, completion):
    state = TaskState(
        model="test-model",
        sample_id="expense",
        epoch=1,
        input=claim_text,
        messages=[],
        output=ModelOutput(completion=completion),
    )
    return asyncio.run(amounts_grounded()(state, state.target))


@pytest.mark.parametrize(
    ("claim_text", "completion", "value", "explanation"),
    [
        (json.dumps(CLAIM), json.dumps(_reply()), CORRECT, "all amounts grounded"),
        (
            json.dumps(CLAIM),
            json.dumps(_reply(claimed=150.0)),
            INCORRECT,
            "claimed_usd is not the converted sum of the lines",
        ),
        (json.dumps(CLAIM), OUT_OF_SCOPE, INCORRECT, "claim or reply is not JSON"),
        ("not a claim", json.dumps(_reply()), INCORRECT, "claim or reply is not JSON"),
        (json.dumps(CLAIM), "[158.0]", INCORRECT, "reply is not a JSON object"),
    ],
    ids=["grounded", "ungrounded", "reply_not_json", "claim_not_json", "reply_not_object"],
)
def test_amounts_grounded_scores_correct_only_for_a_grounded_json_object_reply(
    claim_text, completion, value, explanation
):
    # Witness s17 scorer always correct: `INCORRECT if problem else CORRECT` -> `CORRECT` (scorers.py:80).
    # Witness s17 scorer object check dropped: `if not isinstance(reply, dict):` -> `if False:` (scorers.py:77).
    # Witness s17 scorer explanation dropped: `explanation=problem or "all amounts grounded"` ->
    # `explanation="all amounts grounded"` (scorers.py:80).
    score = _score(claim_text, completion)

    assert (score.value, score.explanation) == (value, explanation)


# end to end, through `aea run`


@pytest.mark.slow
@pytest.mark.parametrize(
    ("factory", "failing"),
    [
        ("build_agent", set()),
        ("build_condensed_agent", {"receipt_missing_over_75", "receipt_missing_after_conversion", "reject_no_receipt"}),
    ],
    ids=["full_prompt", "condensed_prompt"],
)
def test_dataset_run_passes_with_the_full_prompt_and_fails_only_the_receipt_cases_when_condensed(
    tmp_path, factory, failing
):
    # A subprocess, as in test_cli.py: the tracer provider can only be set once per process.
    # Witness s17 condensed drops alcohol (as for active_rules): the alcohol cases fail instead.
    # Witness s17 e2e build_agent condensed: `_build(PROMPT)` -> `_build(PROMPT_CONDENSED)` (agent.py:92).
    command = [sys.executable, "-m", "agent_accelerator.cli", "run", str(DATASET), "--adapter", "langgraph"]
    command += ["--agent", f"examples.expense.agent:{factory}", "--scorer", "examples.expense.scorers:amounts_grounded"]
    command += ["--runs-dir", str(tmp_path)]
    env = {**os.environ, "PYTHONUTF8": "1"}
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr

    (run_dir,) = tmp_path.iterdir()
    results = load_results(run_dir)

    assert len(results.cases) == 12
    assert {case_id for case_id, case in results.cases.items() if not case.passed} == failing


def test_factories_differ_only_in_prompt_and_both_build_a_graph():
    # Witness s17 e2e build_agent condensed (as above): both factories then give the same reply here.
    claim = json.dumps(_claim(_line("taxi", 120.0, receipt=False)))
    replies = [
        json.loads(make().invoke({"messages": [HumanMessage(claim)]})["messages"][-1].content)["approved_usd"]
        for make in (build_agent, build_condensed_agent)
    ]

    assert replies == [0.0, 120.0]


# golden.jsonl


def test_golden_covers_eight_dataset_cases_with_five_labelled_and_the_three_referrals_unlabelled():
    # Witness: "s38 golden new id labelled" labels refer_unsupported_currency; "s38 golden label dropped" removes
    # approve_clean's label; "s38 golden entry renamed" gives refer_over_limit a duplicate.
    golden = load_golden(GOLDEN, {case.id for case in load_dataset(DATASET)})

    unlabelled = sorted(i for i, entry in golden.items() if entry.label is None)
    assert len(golden) == 8
    assert unlabelled == ["refer_over_limit", "refer_over_limit_after_conversion", "refer_unsupported_currency"]
    assert sum(entry.label == "pass" for entry in golden.values()) == 5


def test_every_golden_reference_is_the_reply_the_agent_gives_for_its_case():
    # A reference that drifted from the rules would make the judge fail a correct agent.
    # Witness: "s38 golden reference wrong" sets refer_over_limit_after_conversion's claimed_usd to 5000.0.
    inputs = {case.id: case.input for case in load_dataset(DATASET)}
    golden = load_golden(GOLDEN, set(inputs))

    replies = {
        case_id: json.loads(build_agent().invoke({"messages": [HumanMessage(inputs[case_id])]})["messages"][-1].content)
        for case_id in golden
    }

    assert replies == {case_id: json.loads(entry.reference) for case_id, entry in golden.items()}
