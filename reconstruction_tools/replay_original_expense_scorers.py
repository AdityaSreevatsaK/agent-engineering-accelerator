"""Replay selected original expense scorer assertions against video-restored source.

The original test video draft is copied UNMODIFIED to a temporary test path.
Its recorded one-case disagreement with the recorded scorer source remains
excluded and documented explicitly, without modifying either historical text.

Only local simulated rules / Inspect AI, never live AWS or paid models.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from reconstruction_tools.verify_expense_scorers_video import validate
from reconstruction_tools.verify_original_video_test_candidates import validate_source

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "tests" / "unit" / "test_expense_scorers_REPLAY_TEMP.py"

# IDs are the original video draft's @pytest.mark.parametrize identifiers.
GROUNDING_IDS = (
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
)
KNOWN_DISCREPANCY = "referral_approves_something"


def main() -> int:
    validate()
    source, _ = validate_source("expense")
    # Fail closed if the video source or the video test draft has drifted.
    if ("return \"a referral approves nothing\"" not in
            (ROOT / "examples" / "expense" / "scorers.py").read_text(encoding="utf-8")):
        raise AssertionError("Referral phrase changed since video review")
    if (
        '"referral_approves_something"' not in source
        or '"a referral approves something"' not in source
        or GROUNDING_IDS.count(KNOWN_DISCREPANCY) != 1
        or len(GROUNDING_IDS) != 23
    ):
        raise AssertionError("Original video test/source conflict no longer matches audit")

    if STAGED.exists() or STAGED.is_symlink():
        raise RuntimeError(f"Refusing to overwrite existing file: {STAGED}")
    STAGED.write_text(source, encoding="utf-8", newline="\n")
    nodes = [
        "test_every_dataset_reply_from_the_rule_engine_is_grounded",
        "test_adjustment_approved_usd_given_as_a_bool_is_not_grounded",
        "test_amounts_grounded_scores_correct_only_for_a_grounded_json_object_reply",
    ]
    nodes += [
        f"test_ungrounded_names_the_first_amount_not_traceable_to_the_claim[{id}]"
        for id in GROUNDING_IDS if id != KNOWN_DISCREPANCY
    ]
    rel = STAGED.relative_to(ROOT).as_posix()
    args = [
        sys.executable, "-m", "pytest", "-q", "-m", "not slow", "--maxfail=1",
        *[f"{rel}::{node}" for node in nodes],
    ]
    env = {**os.environ, "AWS_EC2_METADATA_DISABLED": "true",
           "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "",
           "AWS_SESSION_TOKEN": "", "PYTHONUTF8": "1"}
    try:
        print(
            "Running 30 original parameter-expanded scorer assertions "
            "(2 dataset + 22 grounding + 1 boolean + 5 scorer). "
            "One historical video-vs-test referral wording conflict is "
            "EXCLUDED and NOT reported as passed.",
            flush=True,
        )
        return subprocess.call(args, cwd=ROOT, env=env)
    finally:
        STAGED.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
