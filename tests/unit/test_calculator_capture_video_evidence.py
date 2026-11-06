"""Compare source-recorded 10/10 capture facts with the broken screenshot log.

The capture recording establishes the ten original cases all passed, with
capture_content=true. It is NOT a recovered byte-for-byte Inspect JSON log.
We construct an explicitly synthetic *evidence summary* RunResults, never a
fake log or a substitute for the missing original fixtures.
"""

from pathlib import Path

from agent_accelerator.compare import CaseResult, RunResults, Thresholds, compare, load_results
from agent_accelerator.dataset import load_dataset

ROOT = Path(__file__).parents[2]
DATASET = ROOT / "examples" / "calculator" / "dataset.jsonl"
BROKEN = ROOT / "reconstruction_drafts" / "calculator_broken_redacted_SCREENSHOT_CANDIDATE.json"


def test_capture_video_ten_of_ten_against_broken_log_eight_of_ten():
    """The video and screenshots together establish two regression cases."""
    case_ids = {case.id for case in load_dataset(DATASET)}
    assert len(case_ids) == 10
    broken = load_results(BROKEN)
    assert set(broken.cases) == case_ids
    assert broken.status == "success"
    assert broken.capture_content is False
    assert broken.pass_rate == 0.8

    # VIDEO EVIDENCE ONLY: this deliberately is not parsed from a captured log.
    # Do not use it to enable the 58 original fixture-dependent test cases.
    evidence_summary = RunResults(
        run_id="VIDEO_EVIDENCE_ONLY__NOT_AN_ORIGINAL_INSPECT_LOG",
        log_path=Path("DO_NOT_USE_AS_ORIGINAL_CAPTURE_LOG.json"),
        dataset_sha256=broken.dataset_sha256,
        status="success",
        capture_content=True,
        cases={
            case_id: CaseResult(
                id=case_id,
                passed=True,
                error=None,
                latency_s=None,
                failures={},
                runs=1,
                passes=1,
            )
            for case_id in case_ids
        },
    )
    assert evidence_summary.pass_rate == 1.0
    result = compare(evidence_summary, broken, Thresholds())
    assert set(result.newly_failing) == {"subtract", "subtract_large"}
    assert result.newly_passing == []
    assert result.removed == []
    assert result.added == []
    assert result.regressed
