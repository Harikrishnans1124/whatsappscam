"""Pytest test to ensure quantitative evaluation maintains 0 unsafe passes."""

from pathlib import Path

from eval.run_eval import load_cases, run_evaluation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = PROJECT_ROOT / "eval" / "cases.jsonl"


def test_eval_tuning_set_zero_unsafe_passes():
    assert CASES_FILE.exists(), f"Evaluation cases file {CASES_FILE} does not exist"
    cases = load_cases(CASES_FILE, split_filter="tuning")
    assert len(cases) > 0, "No tuning cases found"

    results = run_evaluation(cases, verbose=False)
    assert results["unsafe_passes"] == 0, f"Expected 0 unsafe passes, got {results['unsafe_passes']}"
    assert results["scam_recall"] >= 95.0, f"Expected scam recall >= 95%, got {results['scam_recall']}%"
    assert results["false_alarm_rate"] <= 10.0, f"Expected false alarm rate <= 10%, got {results['false_alarm_rate']}%"


def test_eval_held_out_set_zero_unsafe_passes():
    assert CASES_FILE.exists(), f"Evaluation cases file {CASES_FILE} does not exist"
    cases = load_cases(CASES_FILE, split_filter="held_out")
    assert len(cases) > 0, "No held-out cases found"

    results = run_evaluation(cases, verbose=False)
    assert results["unsafe_passes"] == 0, f"Expected 0 unsafe passes, got {results['unsafe_passes']}"
    assert results["scam_recall"] >= 95.0, f"Expected scam recall >= 95%, got {results['scam_recall']}%"
    assert results["accuracy"] >= 90.0, f"Expected held-out accuracy >= 90%, got {results['accuracy']}%"
