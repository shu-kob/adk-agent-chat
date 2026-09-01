"""
SPECIFICATION_ADDENDUM_v5 §1 & §2 準拠のテスト:
- finish_reason, truncated, thinking_tokens, usage_raw のレコード記録
- truncation_rate および finish_reason 分布、thinking_tokens 統計の集計
"""

import pytest
from eval.guard import create_trial_record, MergeGuard
from eval.aggregator import compute_truncation_metrics, generate_markdown_report


def test_create_trial_record_with_v5_fields():
    record = create_trial_record(
        run_id="test_run_01",
        trial_index=0,
        case_id="struct_01",
        category="structured_output",
        model_id="gemini-3.7-flash",
        provider_route="vertex_ai",
        location="global",
        execution_path="genai_sdk_direct",
        instruction="Test instruction",
        generation_config={"temperature": 0.0, "max_output_tokens": 4096},
        status="success",
        error_type=None,
        latency_ms=500,
        score=1.0,
        raw_output='{"status": "ok"}',
        finish_reason="STOP",
        truncated=False,
        truncation_type=None,
        thinking_tokens=150,
        usage_raw={"prompt_token_count": 50, "candidates_token_count": 20, "thoughts_token_count": 150}
    )

    assert record["finish_reason"] == "STOP"
    assert record["truncated"] is False
    assert record["truncation_type"] is None
    assert record["thinking_tokens"] == 150
    assert record["usage_raw"]["thoughts_token_count"] == 150


def test_compute_truncation_metrics():
    trials = [
        {
            "model_id": "gemini-3.7-flash",
            "category": "multi_step_reasoning",
            "truncated": True,
            "truncation_type": "thinking_dominant",
            "finish_reason": "MAX_TOKENS",
            "thinking_tokens": 980,
            "candidate_tokens": 20
        },
        {
            "model_id": "gemini-3.7-flash",
            "category": "multi_step_reasoning",
            "truncated": False,
            "truncation_type": None,
            "finish_reason": "STOP",
            "thinking_tokens": 500,
            "candidate_tokens": 100
        },
        {
            "model_id": "gemini-3.5-flash-lite",
            "category": "multi_step_reasoning",
            "truncated": True,
            "truncation_type": "output_dominant",
            "finish_reason": "MAX_TOKENS",
            "thinking_tokens": None,
            "candidate_tokens": 1024
        }
    ]

    metrics = compute_truncation_metrics(trials, ["gemini-3.7-flash", "gemini-3.5-flash-lite"])

    flash_m = metrics["by_model"]["gemini-3.7-flash"]
    assert flash_m["total_trials"] == 2
    assert flash_m["truncated_trials"] == 1
    assert flash_m["truncation_rate"] == 0.5
    assert flash_m["thinking_dominant_trials"] == 1
    assert flash_m["thinking_dominant_rate"] == 0.5
    assert flash_m["output_dominant_trials"] == 0
    assert flash_m["finish_reasons"] == {"MAX_TOKENS": 1, "STOP": 1}
    assert flash_m["thinking_tokens_stats"]["available"] is True
    assert flash_m["thinking_tokens_stats"]["count"] == 2
    assert flash_m["thinking_tokens_stats"]["median"] == 740.0

    lite_m = metrics["by_model"]["gemini-3.5-flash-lite"]
    assert lite_m["total_trials"] == 1
    assert lite_m["truncated_trials"] == 1
    assert lite_m["truncation_rate"] == 1.0
    assert lite_m["output_dominant_trials"] == 1
    assert lite_m["thinking_dominant_trials"] == 0
    assert lite_m["finish_reasons"] == {"MAX_TOKENS": 1}
    assert lite_m["thinking_tokens_stats"]["available"] is False
