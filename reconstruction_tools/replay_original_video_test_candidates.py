"""Replay selected originally recorded triage/expense test bodies offline.

The recovered sources are staged as temporary test-only copies under tests/unit
so the original REPO calculation remains valid. Original video candidates are
NEVER modified. The expense scorer has now been recovered at its original path;
both video test sources are staged unmodified, including the original import.
Golden-reference cases, scorer-specific assertions and slow CLI cases are
covered in separate, independently isolated test replay lanes.

This proves behaviour of recorded tests with reconstructed code, NOT full
original-source fidelity or unrelated missing historical fixtures.
"""
from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.verify_original_video_test_candidates import validate_source

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "tests" / "unit"

TRIAGE_TESTS = (
    "test_full_prompt_classifies_each_rule_by_its_trigger_phrases",
    "test_anger_alone_is_not_urgent_billing_and_matching_ignores_case",
    "test_first_matching_rule_in_prompt_order_wins_whatever_the_rules_tuple_order",
    "test_unmatched_ticket_is_other_and_low_only_when_the_prompt_states_the_fallback",
    "test_classifier_reply_is_parsed_from_embedded_json_with_safe_fallbacks",
    "test_each_category_is_routed_to_its_specialist",
    "test_high_priority_billing_ticket_is_escalated_with_the_ticket_as_summary_and_quotes_the_reference",
    "test_only_billing_at_high_priority_is_escalated",
    "test_input_map_writes_only_the_ticket_and_output_map_returns_only_the_three_answer_fields",
    "test_graph_has_no_messages_channel_so_the_adapter_needs_the_input_map",
    "test_reworded_agent_routes_the_planted_tickets_away_from_escalation",
    "test_simulated_classifier_follows_the_prompt_it_is_given_not_the_factory",
    "test_importing_the_agent_does_not_import_langchain_aws",
    "test_live_agent_builds_an_uncompiled_graph_on_bedrock_with_the_region_from_the_environment",
)
EXPENSE_TESTS = (
    "test_full_prompt_activates_every_rule_and_condensed_prompt_lacks_only_the_receipt_rule",
    "test_each_rule_sentence_on_its_own_activates_exactly_that_rule",
    "test_prompt_without_rule_sentences_activates_no_rule",
    "test_plan_looks_up_each_category_once_then_converts_non_usd_lines_then_gets_the_per_diem",
    "test_plan_requests_no_per_diem_unless_the_rule_is_active_and_meals_are_claimed",
    "test_line_over_75_usd_after_conversion_without_receipt_is_rejected",
    "test_line_over_75_usd_without_receipt_is_paid_when_the_receipt_rule_is_inactive",
    "test_alcohol_is_never_reimbursed_and_takes_precedence_over_the_receipt_rule",
    "test_alcohol_is_paid_when_the_alcohol_rule_is_inactive",
    "test_meals_are_capped_at_the_per_diem_in_line_order_until_the_allowance_is_exhausted",
    "test_meals_are_not_capped_when_the_per_diem_rule_is_inactive",
    "test_meal_rejected_for_no_receipt_does_not_use_up_the_per_diem",
    "test_lodging_is_capped_at_the_nightly_limit_times_days_with_the_senior_limit_from_grade_4",
    "test_claim_over_5000_usd_after_conversion_is_referred_without_a_decision",
    "test_claim_at_5000_usd_or_with_the_refer_rule_inactive_is_decided",
    "test_claim_with_an_unconvertible_currency_is_referred_naming_the_first_such_line",
    "test_unconvertible_line_counts_as_zero_when_the_currency_referral_rule_is_inactive",
    "test_convert_currency_uses_the_fixed_usd_rates_rounded_to_cents",
    "test_convert_currency_rejects_an_unsupported_currency_without_echoing_it",
    "test_per_diem_is_the_city_daily_allowance_times_days",
    "test_lookup_policy_returns_the_lodging_limits_and_a_generic_rule_for_an_unknown_category",
    "test_input_that_is_not_a_json_claim_with_lines_gets_the_out_of_scope_reply",
    "test_agent_reply_is_the_review_of_the_claim_and_a_tool_error_becomes_a_currency_referral",
    "test_factories_differ_only_in_prompt_and_both_build_a_graph",
)
SCORER_IMPORT = "from examples.expense.scorers import amounts_grounded, ungrounded  # noqa: E402"


def run_suite(name: str) -> int:
    source, tree = validate_source(name)
    names = TRIAGE_TESTS if name == "triage" else EXPENSE_TESTS
    existing = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    }
    if len(set(names)) != len(names) or set(names) - set(existing):
        raise RuntimeError(f"{name}: replay selection changed or historical tests disappeared")
    for func_name in names:
        node = existing[func_name]
        params = {a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
        if "check_runs" in params or "runs" in params or "price_runs" in params:
            raise RuntimeError(f"{name}: selected original test unexpectedly requires CLI fixtures: {func_name}")
    if name == "expense":
        if source.count(SCORER_IMPORT) != 1:
            raise RuntimeError("Historical expense source scorer import missing or altered")
        if not (ROOT / "examples" / "expense" / "scorers.py").is_file():
            raise RuntimeError("Recovered original expense scorer source unavailable")
    staged = STAGED / f"test_{name}_video_source_REPLAY_TEMP.py"
    ast.parse(source, filename=str(staged), feature_version=(3, 11))
    if staged.exists() or staged.is_symlink():
        raise RuntimeError(f"Refusing to replace existing source: {staged}")
    staged.write_text(source, encoding="utf-8", newline="\n")
    try:
        path = staged.relative_to(ROOT).as_posix()
        args = [sys.executable, "-m", "pytest", "-q", "-m", "not slow", "--maxfail=1"]
        args += [f"{path}::{test_name}" for test_name in names]
        env = {
            **os.environ,
            "AWS_EC2_METADATA_DISABLED": "true", "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "", "AWS_SESSION_TOKEN": "", "PYTHONUTF8": "1",
        }
        print(
            f"Executing {len(names)} original-video {name} test functions with "
            "original parameterisations, original imports, and no paid cloud calls.",
            flush=True,
        )
        return subprocess.call(args, cwd=ROOT, env=env)
    finally:
        staged.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("triage", "expense", "all"), default="all")
    x = parser.parse_args()
    selected = ("triage", "expense") if x.suite == "all" else (x.suite,)
    bad = [name for name in selected if run_suite(name) != 0]
    if bad:
        print(f"Offline original-test replay failed: {bad}", file=sys.stderr)
        return 1
    print("Selected reconstructed original test bodies passed offline.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
