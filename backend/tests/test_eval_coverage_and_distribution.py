"""
Unit Tests for Phase 4 Coverage, Common Case Matrix, and Failure Distribution (backend/tests/test_eval_coverage_and_distribution.py)
"""

import pytest
from eval.aggregator import (
    compute_coverage_metrics,
    compute_common_case_matrix,
    compute_failure_distribution_metrics,
    format_coverage_cell,
    generate_markdown_report
)

def test_compute_coverage_metrics():
    # 2モデル, 各2ケース, 各2試行のサンプルデータ
    # model_A: case_1 は全成功、case_2 は1成功1失敗
    # model_B: case_1 は全成功、case_2 は全失敗 (未測定)
    case_summary = {
        ("c1", "model_A"): {"category": "cat1", "model_id": "model_A", "median_score": 1.0, "successful_trials": 2, "total_trials": 2, "min_score": 1.0, "max_score": 1.0},
        ("c2", "model_A"): {"category": "cat1", "model_id": "model_A", "median_score": 0.5, "successful_trials": 1, "total_trials": 2, "min_score": 0.5, "max_score": 0.5},
        ("c1", "model_B"): {"category": "cat1", "model_id": "model_B", "median_score": 1.0, "successful_trials": 2, "total_trials": 2, "min_score": 1.0, "max_score": 1.0},
        ("c2", "model_B"): {"category": "cat1", "model_id": "model_B", "median_score": None, "successful_trials": 0, "total_trials": 2, "min_score": None, "max_score": None, "error_type": "ResourceExhausted"},
    }
    all_cases = [
        {"case_id": "c1", "category": "cat1"},
        {"case_id": "c2", "category": "cat1"}
    ]

    cov = compute_coverage_metrics(case_summary, all_cases, ["model_A", "model_B"])

    # model_A: 2/2 cases measured (100%), 3/4 trials (75%)
    assert cov["model_A"]["cat1"]["measured_cases"] == 2
    assert cov["model_A"]["cat1"]["total_cases"] == 2
    assert cov["model_A"]["cat1"]["case_coverage"] == 1.0
    assert cov["model_A"]["cat1"]["measured_trials"] == 3
    assert cov["model_A"]["cat1"]["total_trials"] == 4
    assert cov["model_A"]["cat1"]["trial_coverage"] == 0.75

    # model_B: 1/2 cases measured (50%), 2/4 trials (50%)
    assert cov["model_B"]["cat1"]["measured_cases"] == 1
    assert cov["model_B"]["cat1"]["total_cases"] == 2
    assert cov["model_B"]["cat1"]["case_coverage"] == 0.5
    assert cov["model_B"]["cat1"]["unmeasured_cases"] == ["c2"]

def test_format_coverage_cell():
    # 満点 4, 測定 6, 総ケース 10, スコア 91.1%
    cell = format_coverage_cell(
        score=0.911,
        perfect_cases=4,
        measured_cases=6,
        total_cases=10
    )
    assert cell == "91.1% (満点 4/6, 測定 6/10) ⚠️"

    # カバレッジ 100% の場合
    cell_full = format_coverage_cell(
        score=1.0,
        perfect_cases=10,
        measured_cases=10,
        total_cases=10
    )
    assert cell_full == "100.0% (満点 10/10, 測定 10/10)"

def test_compute_common_case_matrix():
    case_summary = {
        ("c1", "model_A"): {"category": "cat1", "median_score": 1.0},
        ("c2", "model_A"): {"category": "cat1", "median_score": 0.8},
        ("c1", "model_B"): {"category": "cat1", "median_score": 0.9},
        ("c2", "model_B"): {"category": "cat1", "median_score": None}, # 未測定
    }
    all_cases = [
        {"case_id": "c1", "category": "cat1"},
        {"case_id": "c2", "category": "cat1"}
    ]

    common_matrix, common_cases_count, excluded_count = compute_common_case_matrix(
        case_summary, all_cases, ["model_A", "model_B"]
    )

    # 共通測定されたのは c1 のみ (1ケース)
    assert common_cases_count == 1
    assert excluded_count == 1
    assert common_matrix["cat1"]["model_A"]["score"] == 1.0
    assert common_matrix["cat1"]["model_B"]["score"] == 0.9

def test_compute_failure_distribution_metrics():
    # cat1: c1=1.0, c2=1.0, c3=0.0 (集中型失敗)
    case_scores = [1.0, 1.0, 0.0]
    dist = compute_failure_distribution_metrics(case_scores)
    assert dist["perfect_case_ratio"] == pytest.approx(2/3, 0.01)
    assert dist["zero_case_ratio"] == pytest.approx(1/3, 0.01)
    assert dist["score_stddev"] > 0.4
