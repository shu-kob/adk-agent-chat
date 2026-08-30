"""
Unit Tests for Phase 3 Traffic Capture & Storage (backend/tests/test_traffic_store.py)
"""

import os
import json
import pytest
import tempfile
from datetime import datetime, timedelta
from eval.traffic.store import TrafficStore, default_pii_masking_hook

@pytest.fixture
def temp_traffic_file():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        file_path = f.name
    yield file_path
    if os.path.exists(file_path):
        os.remove(file_path)

def test_record_interaction_schema_and_persistence(temp_traffic_file):
    store = TrafficStore(log_file_path=temp_traffic_file)

    context = [
        {"role": "user", "text": "こんにちは"},
        {"role": "assistant", "text": "こんにちは！何かお手伝いできますか？"}
    ]
    gen_config = {"temperature": 0.7, "max_output_tokens": 1024}

    record = store.record_interaction(
        session_id="sess_12345",
        input_text="おすすめのプログラミング言語は？",
        conversation_context=context,
        output_text="PythonやTypeScriptが人気です。",
        model_id="gemini-3.7-flash",
        provider_route="vertex_ai",
        instruction="You are a helpful assistant.",
        generation_config=gen_config,
        latency_ms=1200
    )

    # 1. 戻り値のスキーマ検証 (11フィールド)
    assert "query_id" in record
    assert "timestamp" in record
    assert record["session_id"] == "sess_12345"
    assert record["input_text"] == "おすすめのプログラミング言語は？"
    assert record["conversation_context"] == context
    assert record["output_text"] == "PythonやTypeScriptが人気です。"
    assert record["model_id"] == "gemini-3.7-flash"
    assert record["provider_route"] == "vertex_ai"
    assert "instruction_hash" in record
    assert record["generation_config"] == gen_config
    assert record["latency_ms"] == 1200

    # 2. JSONL ファイルの永続化検証
    with open(temp_traffic_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    saved_data = json.loads(lines[0])
    assert saved_data["query_id"] == record["query_id"]
    assert saved_data["input_text"] == "おすすめのプログラミング言語は？"

def test_masking_hook_filters_pii(temp_traffic_file):
    # マスキングフック付きでストアを初期化
    store = TrafficStore(log_file_path=temp_traffic_file, masking_hook=default_pii_masking_hook)

    record = store.record_interaction(
        session_id="sess_mask_test",
        input_text="私のメールアドレスは test.user@example.com、電話番号は 090-1234-5678 です。",
        conversation_context=[],
        output_text="承知いたしました。test.user@example.com 宛てにご案内します。",
        model_id="gemini-3.7-flash",
        provider_route="ai_studio",
        instruction="You are a helpful assistant.",
        generation_config={},
        latency_ms=800
    )

    # メールアドレスと電話番号がマスクされているか検証
    assert "test.user@example.com" not in record["input_text"]
    assert "[EMAIL]" in record["input_text"]
    assert "090-1234-5678" not in record["input_text"]
    assert "[PHONE]" in record["input_text"]

    assert "test.user@example.com" not in record["output_text"]
    assert "[EMAIL]" in record["output_text"]

def test_query_interactions_filtering_and_sampling(temp_traffic_file):
    store = TrafficStore(log_file_path=temp_traffic_file)

    for i in range(10):
        store.record_interaction(
            session_id=f"sess_{i}",
            input_text=f"Question {i}",
            conversation_context=[],
            output_text=f"Answer {i}",
            model_id="gemini-3.7-flash",
            provider_route="vertex_ai",
            instruction="System prompt",
            generation_config={},
            latency_ms=100 * (i + 1)
        )

    # 全件取得
    all_records = store.query_interactions()
    assert len(all_records) == 10

    # 件数上限 (limit)
    limited = store.query_interactions(limit=5)
    assert len(limited) == 5

    # サンプリング
    sampled = store.query_interactions(sample_ratio=0.5, seed=42)
    assert 3 <= len(sampled) <= 7
