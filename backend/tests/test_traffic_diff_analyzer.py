"""
Unit Tests for Phase 3 Deterministic Diff Analyzer (backend/tests/test_traffic_diff_analyzer.py)
"""

import pytest
from eval.traffic.diff_analyzer import (
    compute_deterministic_diff_metrics,
    calculate_levenshtein_similarity,
    generate_replay_diff_report
)

def test_calculate_levenshtein_similarity():
    # 完全一致
    assert calculate_levenshtein_similarity("Hello World", "Hello World") == 1.0
    # 完全に異なる
    assert calculate_levenshtein_similarity("abc", "xyz") == 0.0
    # 部分一致
    sim = calculate_levenshtein_similarity("Python 3.11", "Python 3.12")
    assert 0.8 < sim < 1.0

def test_compute_deterministic_diff_metrics():
    records = [
        {
            "candidate_id": "cand_A",
            "model_id": "gemini-3.7-flash",
            "input_text": "Q1",
            "original_output": "東京は日本の首都です。",
            "raw_output": "東京は日本の首都です。",
            "latency_ms": 500,
            "status": "success"
        },
        {
            "candidate_id": "cand_A",
            "model_id": "gemini-3.7-flash",
            "input_text": "Q2",
            "original_output": "1+1は2です。",
            "raw_output": "```json\n{\"result\": 2}\n```",
            "latency_ms": 600,
            "status": "success"
        },
        {
            "candidate_id": "cand_B",
            "model_id": "gemini-3.5-flash-lite",
            "input_text": "Q1",
            "original_output": "東京は日本の首都です。",
            "raw_output": "日本の首都は東京です。",
            "latency_ms": 300,
            "status": "success"
        },
        {
            "candidate_id": "cand_B",
            "model_id": "gemini-3.5-flash-lite",
            "input_text": "Q2",
            "original_output": "1+1は2です。",
            "raw_output": "{\"result\": 2}",
            "latency_ms": 350,
            "status": "success"
        }
    ]

    metrics = compute_deterministic_diff_metrics(records)

    assert "cand_A" in metrics
    assert "cand_B" in metrics

    # cand_A のメトリクス検証
    stats_a = metrics["cand_A"]
    assert stats_a["total_queries"] == 2
    assert stats_a["exact_match_count"] == 1  # Q1 is exact match
    assert stats_a["exact_match_ratio"] == 0.5
    assert stats_a["valid_json_count"] == 1   # Q2 is valid json (inside markdown fence)
    assert stats_a["has_markdown_fence_count"] == 1  # Q2 has ```
    assert stats_a["avg_similarity_to_original"] > 0.5

    # cand_B のメトリクス検証
    stats_b = metrics["cand_B"]
    assert stats_b["exact_match_count"] == 0
    assert stats_b["valid_json_count"] == 1
    assert stats_b["has_markdown_fence_count"] == 0

def test_generate_replay_diff_report():
    job_summary = {
        "job_id": "job_test_001",
        "started_at": "2026-08-30T14:00:00",
        "completed_at": "2026-08-30T14:00:10",
        "duration_sec": 10.0,
        "total_queries_processed": 2,
        "total_candidates": 2,
        "total_cost_usd": 0.00012
    }
    metrics = {
        "cand_3.7": {
            "model_id": "gemini-3.7-flash",
            "total_queries": 2,
            "exact_match_ratio": 0.5,
            "avg_similarity_to_original": 0.85,
            "valid_json_ratio": 0.5,
            "has_markdown_fence_ratio": 0.5,
            "avg_char_length": 15.0,
            "avg_latency_ms": 550.0
        },
        "cand_3.5": {
            "model_id": "gemini-3.5-flash-lite",
            "total_queries": 2,
            "exact_match_ratio": 0.0,
            "avg_similarity_to_original": 0.70,
            "valid_json_ratio": 0.5,
            "has_markdown_fence_ratio": 0.0,
            "avg_char_length": 12.0,
            "avg_latency_ms": 325.0
        }
    }

    report = generate_replay_diff_report(job_summary, metrics)
    assert "# 🔁 Replay Evaluation Diff Analysis Report" in report
    assert "`cand_3.7`" in report
    assert "`cand_3.5`" in report
    assert "完全一致率" in report
    assert "平均類似度" in report
