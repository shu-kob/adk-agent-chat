"""
Gemini Batch API & FinOps 連携機能 受け入れテスト (ATDD)
(backend/tests/test_batch_eval.py)

【受け入れ条件】
- AC-1: calculate_cost_savings
  - オンデマンド vs Batch API (50% OFF) の料金試算
  - 1,000円 (JPY) で処理可能なバッチ推論件数 (capacity_for_1000_jpy) が計算されること
- AC-2: submit_batch_job
  - バッチリクエスト JSONL を生成し、ジョブ ID、件数、ステータスを返却すること
- AC-3: GET /api/eval/batch/finops および POST /api/eval/batch/submit
  - エンドポイント経由で試算およびジョブ投入が正常完了すること
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from eval.traffic.batch import GeminiBatchManager
from main import app

client = TestClient(app)


class TestBatchFinOpsAcceptanceCriteria:
    """AC-1 & AC-2: GeminiBatchManager の試算およびジョブ管理"""

    def test_calculate_cost_savings_with_1000_jpy_capacity(self):
        """1,000円での処理可能件数を含む FinOps 試算が算出されること"""
        manager = GeminiBatchManager(candidate_model_id="gemini-3.5-flash-lite")
        savings = manager.calculate_cost_savings(total_queries=100)

        assert savings["discount_percentage"] == "50.0%"
        assert savings["batch_cost_usd"] == round(savings["ondemand_cost_usd"] * 0.5, 6)
        assert "capacity_for_1000_jpy" in savings
        assert savings["capacity_for_1000_jpy"] > 10000  # 3.5-flash-liteなら1,000円で数万件以上処理可能

    def test_submit_batch_job_and_status(self, tmp_path):
        """バッチジョブの投入とステータス取得"""
        batch_file = str(tmp_path / "test_batch.jsonl")
        manager = GeminiBatchManager(candidate_model_id="gemini-3.8-flash")
        
        job_result = manager.submit_batch_job(limit=5, output_path=batch_file)
        assert "job_id" in job_result
        assert job_result["status"] in ["submitted", "completed", "running"]
        assert job_result["total_queries"] >= 3
        assert "input_file_path" in job_result
        # AC: 品質・回帰検証メトリクスと出力プレビューの検証
        assert "metrics" in job_result
        assert job_result["metrics"]["format_error_count"] == 0
        assert "consistency_score" in job_result["metrics"]
        assert "preview_items" in job_result
        assert len(job_result["preview_items"]) >= 1
        assert "input_text" in job_result["preview_items"][0]
        assert "batch_output" in job_result["preview_items"][0]


class TestBatchApiEndpoints:
    """AC-3: REST API エンドポイントの検証"""

    def test_get_batch_finops_endpoint(self):
        """GET /api/eval/batch/finops が capacity_for_1000_jpy を含んで正常応答すること"""
        resp = client.get("/api/eval/batch/finops")
        assert resp.status_code == 200
        data = resp.json()
        assert "savings" in data
        assert "report_markdown" in data
        assert "capacity_for_1000_jpy" in data["savings"]

    def test_post_batch_submit_endpoint(self):
        """POST /api/eval/batch/submit でバッチジョブが投入できること"""
        resp = client.post("/api/eval/batch/submit", json={
            "limit": 5,
            "model_id": "gemini-3.5-flash-lite"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "job" in data
        assert "job_id" in data["job"]
        assert "metrics" in data["job"]
        assert "preview_items" in data["job"]
