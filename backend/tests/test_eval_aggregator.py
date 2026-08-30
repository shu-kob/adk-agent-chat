import pytest
from eval.aggregator import (
    aggregate_trials_by_case,
    compute_category_matrix,
    detect_unstable_cases,
    format_percentage_with_sample_size,
    generate_markdown_report
)

def test_aggregate_trials_by_case_computes_median_and_spread():
    # 3 trials for same case & model with scores 0.8, 1.0, 0.9
    trials = [
        {"case_id": "c1", "category": "cat1", "model_id": "m1", "score": 0.8, "status": "success", "latency_ms": 1000},
        {"case_id": "c1", "category": "cat1", "model_id": "m1", "score": 1.0, "status": "success", "latency_ms": 1200},
        {"case_id": "c1", "category": "cat1", "model_id": "m1", "score": 0.9, "status": "success", "latency_ms": 1100}
    ]
    summary = aggregate_trials_by_case(trials)
    assert ("c1", "m1") in summary
    res = summary[("c1", "m1")]
    assert res["median_score"] == 0.9
    assert res["min_score"] == 0.8
    assert res["max_score"] == 1.0
    assert res["trial_count"] == 3
    assert res["success_count"] == 3
    assert res["is_unstable"] is True  # 0.8 != 1.0

def test_aggregate_trials_handles_error_records():
    trials = [
        {"case_id": "c1", "category": "cat1", "model_id": "m1", "score": 1.0, "status": "success", "latency_ms": 1000},
        {"case_id": "c1", "category": "cat1", "model_id": "m1", "score": None, "status": "error", "error_type": "Timeout", "latency_ms": 20000},
        {"case_id": "c1", "category": "cat1", "model_id": "m1", "score": 1.0, "status": "success", "latency_ms": 1100}
    ]
    summary = aggregate_trials_by_case(trials)
    res = summary[("c1", "m1")]
    assert res["median_score"] == 1.0
    assert res["success_count"] == 2
    assert res["error_count"] == 1

def test_detect_unstable_cases():
    summary = {
        ("c1", "m1"): {"case_id": "c1", "category": "cat1", "model_id": "m1", "is_unstable": True, "min_score": 0.5, "max_score": 1.0, "trial_count": 3},
        ("c2", "m1"): {"case_id": "c2", "category": "cat1", "model_id": "m1", "is_unstable": False, "min_score": 1.0, "max_score": 1.0, "trial_count": 3}
    }
    unstable = detect_unstable_cases(summary)
    assert len(unstable) == 1
    assert unstable[0]["case_id"] == "c1"

def test_format_percentage_with_sample_size():
    # 2 out of 3 cases passed with 100% -> 66.7% (2/3)
    text = format_percentage_with_sample_size(score_pct=66.7, count=2, total=3)
    assert text == "66.7% (2/3) ⚠️"  # total < 5 gets warning note
    
    text_large = format_percentage_with_sample_size(score_pct=80.0, count=8, total=10)
    assert text_large == "80.0% (8/10)"

def test_generate_markdown_report_includes_execution_conditions_and_no_assertions():
    batch_meta = {
        "run_id": "run_test_001",
        "provider_route": "vertex_ai",
        "location": "global",
        "trials_per_case": 3,
        "temperature": 0.0,
        "dataset_version": "v1.0.0",
        "models": ["gemini-2.5-flash"]
    }
    category_matrix = {
        "structured_output": {
            "gemini-2.5-flash": {"score_pct": 100.0, "passed": 3, "total": 3, "avg_latency_s": 2.1}
        }
    }
    unstable_cases = []

    report = generate_markdown_report(batch_meta, category_matrix, unstable_cases)
    assert "## 1. 実行条件サマリ" in report
    assert "vertex_ai" in report
    assert "temperature: 0.0" in report
    assert "100.0% (3/3) ⚠️" in report
    # No subjective recommendations
    assert "最適" not in report
    assert "推奨" not in report
