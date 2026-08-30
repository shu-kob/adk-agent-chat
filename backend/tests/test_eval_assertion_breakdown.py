import pytest
from eval.aggregator import (
    compute_assertion_failure_breakdown,
    generate_markdown_report
)

def test_compute_assertion_failure_breakdown():
    trial_records = [
        {
            "model_id": "gemini-2.5-flash",
            "category": "structured_output",
            "case_id": "struct_01",
            "status": "success",
            "assertions": [
                {"name": "no_markdown_fence", "passed": False, "detail": "Contains ```"},
                {"name": "valid_json_syntax", "passed": True, "detail": "Valid JSON"}
            ]
        },
        {
            "model_id": "gemini-2.5-flash",
            "category": "structured_output",
            "case_id": "struct_02",
            "status": "success",
            "assertions": [
                {"name": "no_markdown_fence", "passed": False, "detail": "Contains ```"},
                {"name": "valid_json_syntax", "passed": True, "detail": "Valid JSON"}
            ]
        },
        {
            "model_id": "gemini-2.5-flash",
            "category": "negative_constraint",
            "case_id": "neg_01",
            "status": "success",
            "assertions": [
                {"name": "forbidden_word__AI", "passed": False, "detail": "Contains AI"}
            ]
        }
    ]

    breakdown = compute_assertion_failure_breakdown(trial_records)
    assert "gemini-2.5-flash" in breakdown
    model_breakdown = breakdown["gemini-2.5-flash"]
    assert "structured_output" in model_breakdown
    assert model_breakdown["structured_output"]["no_markdown_fence"] == 2
    assert "negative_constraint" in model_breakdown
    assert model_breakdown["negative_constraint"]["forbidden_word__AI"] == 1

def test_markdown_report_includes_assertion_breakdown():
    batch_meta = {
        "run_id": "run_001",
        "provider_route": "vertex_ai",
        "location": "global",
        "trials_per_case": 3,
        "temperature": 0.0,
        "dataset_version": "v2.0.0",
        "models": ["gemini-2.5-flash"]
    }
    category_matrix = {
        "structured_output": {
            "gemini-2.5-flash": {"score_pct": 80.0, "passed": 8, "total": 10, "avg_latency_s": 2.5}
        }
    }
    unstable_cases = []
    assertion_failures = {
        "gemini-2.5-flash": {
            "structured_output": {"no_markdown_fence": 2}
        }
    }

    report = generate_markdown_report(
        batch_meta,
        category_matrix,
        unstable_cases,
        assertion_failures=assertion_failures
    )

    assert "## 3. アサーション別 失敗内訳 (制約違反の分析)" in report
    assert "`no_markdown_fence`" in report
    assert "2 回失敗" in report or "2" in report
