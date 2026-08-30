import pytest
import os
from eval.dataset import load_benchmark_dataset, DATASET_VERSION_V2

def test_load_benchmark_dataset_returns_enabled_cases_only_by_default():
    cases = load_benchmark_dataset(include_disabled=False)
    assert len(cases) >= 30
    for case in cases:
        assert case.get("enabled", True) is True

def test_load_benchmark_dataset_categories_and_counts():
    cases = load_benchmark_dataset(include_disabled=False)
    categories = {}
    for case in cases:
        cat = case["category"]
        categories[cat] = categories.get(cat, 0) + 1

    assert "structured_output" in categories
    assert "negative_constraint" in categories
    assert "multi_step_reasoning" in categories
    
    assert categories["structured_output"] >= 10
    assert categories["negative_constraint"] >= 10
    assert categories["multi_step_reasoning"] >= 10

def test_load_benchmark_dataset_includes_disabled_when_requested():
    all_cases = load_benchmark_dataset(include_disabled=True)
    disabled_cases = [c for c in all_cases if not c.get("enabled", True)]
    
    assert len(disabled_cases) >= 4  # long_context (2) + ambiguous_intent (2)
    disabled_cats = set(c["category"] for c in disabled_cases)
    assert "long_context_retrieval" in disabled_cats
    assert "ambiguous_intent" in disabled_cats

def test_case_schema_completeness():
    cases = load_benchmark_dataset(include_disabled=True)
    valid_difficulties = {"basic", "intermediate", "advanced"}

    for case in cases:
        assert "id" in case
        assert "category" in case
        assert "title" in case
        assert "difficulty" in case
        assert case["difficulty"] in valid_difficulties
        assert "max_output_tokens" in case
        assert isinstance(case["max_output_tokens"], int)
        assert "prompt" in case
        assert "eval_type" in case
        assert "expected" in case
