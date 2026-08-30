"""
Unit Tests for Phase 3 Replay Execution Job (backend/tests/test_replay_job.py)
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from eval.traffic.store import TrafficStore
from eval.traffic.replay import ReplayJob, ReplayCandidate

@pytest.fixture
def populated_traffic_store():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        file_path = f.name
    
    store = TrafficStore(log_file_path=file_path)
    # テスト用に対話ログを3件保存
    for i in range(3):
        store.record_interaction(
            session_id=f"sess_{i}",
            input_text=f"User question {i}",
            conversation_context=[{"role": "user", "text": f"Previous turn {i}"}],
            output_text=f"Original output {i}",
            model_id="gemini-3.5-flash-lite",
            provider_route="vertex_ai",
            instruction="Original instruction",
            generation_config={"temperature": 0.0},
            latency_ms=500
        )
    
    yield store
    if os.path.exists(file_path):
        os.remove(file_path)

def test_replay_job_executes_multiple_candidates(populated_traffic_store):
    # 3候補の定義 (モデル/プロンプト/パラメータの組み合わせ)
    candidates = [
        ReplayCandidate(
            candidate_id="cand_3.7_flash",
            model_id="gemini-3.7-flash",
            instruction="You are a helpful assistant.",
            generation_config={"temperature": 0.0, "max_output_tokens": 512}
        ),
        ReplayCandidate(
            candidate_id="cand_3.5_lite",
            model_id="gemini-3.5-flash-lite",
            instruction="You are a concise assistant.",
            generation_config={"temperature": 0.0, "max_output_tokens": 256}
        ),
        ReplayCandidate(
            candidate_id="cand_3.1_pro",
            model_id="gemini-3.1-pro-preview",
            instruction="You are an expert assistant.",
            generation_config={"temperature": 0.0, "max_output_tokens": 1024}
        )
    ]

    job = ReplayJob(traffic_store=populated_traffic_store, candidates=candidates)

    # API 呼び出しのモック
    mock_generate = MagicMock(return_value=("Replayed response text", 50, 20))
    with patch("eval.traffic.replay.generate_replay_content", mock_generate):
        results = job.run(limit=2)

    # 1. 実行件数・メタデータの検証
    assert results["total_queries_processed"] == 2
    assert results["total_candidates"] == 3
    assert len(results["records"]) == 2 * 3  # 2 queries * 3 candidates = 6 records

    # 2. 各レコードのスキーマ検証 (Phase 1.4 互換 + Phase 3 拡張)
    for rec in results["records"]:
        assert rec["source"] == "replay"
        assert "candidate_id" in rec
        assert rec["candidate_id"] in ["cand_3.7_flash", "cand_3.5_lite", "cand_3.1_pro"]
        assert "query_id" in rec
        assert "prompt_tokens" in rec
        assert "candidate_tokens" in rec
        assert "cost_usd" in rec
        assert rec["raw_output"] == "Replayed response text"
