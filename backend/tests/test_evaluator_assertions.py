import pytest
from eval.evaluator import Evaluator

def test_eval_json_schema_detailed_assertions():
    text = '{"order_id": "ORD-123", "customer_name": "山田", "items": [{"name": "A", "quantity": 1, "unit_price": 100}], "shipping_fee": 500, "discount": 0, "total_amount": 600}'
    expected = {
        "order_id": "ORD-123",
        "customer_name": "山田",
        "items_count": 1,
        "shipping_fee": 500,
        "discount": 0,
        "total_amount": 600
    }
    score, reasons, assertions = Evaluator.evaluate_detailed("json_schema", text, expected)
    
    assert score == 1.0
    assert len(assertions) >= 3
    assertion_names = [a["name"] for a in assertions]
    assert "no_markdown_fence" in assertion_names
    assert "valid_json_syntax" in assertion_names
    assert all(a["passed"] for a in assertions)

def test_eval_json_schema_partial_failure():
    # Has markdown fence and wrong total_amount
    text = '```json\n{"order_id": "ORD-123", "customer_name": "山田", "items": [], "shipping_fee": 500, "discount": 0, "total_amount": 9999}\n```'
    expected = {
        "order_id": "ORD-123",
        "customer_name": "山田",
        "items_count": 0,
        "shipping_fee": 500,
        "discount": 0,
        "total_amount": 600
    }
    score, reasons, assertions = Evaluator.evaluate_detailed("json_schema", text, expected)
    
    # 1 fence fail, 1 value fail out of multiple checks -> score < 1.0 but > 0.0
    assert 0.0 < score < 1.0
    failed_assertions = [a["name"] for a in assertions if not a["passed"]]
    assert "no_markdown_fence" in failed_assertions
    assert "field_match__total_amount" in failed_assertions

def test_eval_negative_rules_detailed_assertions():
    # Violates forbidden word 'AI' and length constraint
    text = "AIの進歩はすごいです。"
    expected = {
        "forbidden_words": ["AI", "人工知能"],
        "min_length": 60,
        "max_length": 140
    }
    score, reasons, assertions = Evaluator.evaluate_detailed("negative_rules", text, expected)
    assert score < 1.0
    failed_names = [a["name"] for a in assertions if not a["passed"]]
    assert "forbidden_word__AI" in failed_names
    assert "min_length_check" in failed_names

def test_eval_no_katakana():
    text = "電子計算機は計算を行う装置です。"
    expected = {"forbid_katakana": True, "min_length": 10}
    score, reasons, assertions = Evaluator.evaluate_detailed("no_katakana", text, expected)
    assert score == 1.0
    assert all(a["passed"] for a in assertions)

    text_with_katakana = "パソコンは便利です。"
    score_fail, _, assertions_fail = Evaluator.evaluate_detailed("no_katakana", text_with_katakana, expected)
    assert score_fail < 1.0
    assert any(not a["passed"] and a["name"] == "no_katakana_check" for a in assertions_fail)
