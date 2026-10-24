"""
動的モデルルーティング (Contextual Router) 受け入れテスト
(backend/tests/test_dynamic_router.py)

【ATDD 受け入れ条件】
- AC-1: route_model_for_query
  - 高度推論・分析・政策・コード生成 ➔ gemini-3.8-flash
  - 日常会話・雑談・共感・即答・家計相談 ➔ gemini-3.5-flash-lite
- AC-2: /api/chat で routing_mode="auto" (または model="dynamic-router") 指定時
  - 判定結果に基づき選択されたモデルで推論実行
  - レスポンスの model に選定モデル、routed_info に判定詳細が付与されること
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# まだ未実装のモジュールをインポート（Red 確認用）
from eval.traffic.router import route_model_for_query, DynamicRouter
from main import app


@pytest.fixture
def anyio_backend():
    return 'asyncio'


class TestDynamicRouterAcceptanceCriteria:
    """AC-1: クエリ分類とモデルルーティングエンジンの検証"""

    def test_routes_complex_reasoning_to_gemini_3_8_flash(self):
        """高度推論・マクロ経済・政策・プログラミング等は gemini-3.8-flash へルーティング"""
        queries = [
            "食料品の消費税を2年間1%に減税した場合のマクロ経済と財政影響を多角的に試算してください",
            "Pythonでasyncioとマルチスレッドを組み合わせる場合のメモリ安全設計とサンプルコード",
            "医療法および医師法におけるオンライン診療の法的責任と最新のガイドライン基準について",
            "大規模分散システムにおけるCAP定理とPaxos/Raft合意アルゴリズムのトレードオフ分析"
        ]
        for q in queries:
            result = route_model_for_query(q)
            assert result["model_id"] == "gemini-3.8-flash", f"Failed for query: {q}"
            assert result["category"] in ["complex_reasoning", "technical_code", "policy_analysis"]
            assert "reason" in result

    def test_routes_casual_and_empathy_to_gemini_3_5_flash_lite(self):
        """日常会話・挨拶・雑談・共感・家計の相談等は gemini-3.5-flash-lite へルーティング"""
        queries = [
            "こんにちは！今日も一日お疲れ様です",
            "寿司が世界中で愛されている理由って何だと思う？",
            "家計のやりくりで食費を抑えるコツを教えて！3人家族です",
            "最近仕事が忙しくて少し疲れたよ",
            "今日の夕飯、冷蔵庫に豚肉とキャベツがあるんだけど何作ろう？"
        ]
        for q in queries:
            result = route_model_for_query(q)
            assert result["model_id"] == "gemini-3.5-flash-lite", f"Failed for query: {q}"
            assert result["category"] in ["casual_conversation", "empathy_lifestyle", "general_qa"]
            assert "reason" in result


class TestDynamicRouterApiIntegration:
    """AC-2: /api/chat エンドポイントにおける動的ルーティング統合の検証"""

    def test_chat_endpoint_with_dynamic_routing_auto(self, monkeypatch):
        """routing_mode='auto' 時にクエリに応じて動的にモデルが選定され、メタデータが返却されること"""
        from unittest.mock import AsyncMock
        from agent import agent_manager
        mock_generate = AsyncMock(return_value="動的ルーティングされた回答です")
        monkeypatch.setattr(agent_manager, "generate_response", mock_generate)

        client = TestClient(app)

        # 1. 複雑推論クエリ ➔ gemini-3.8-flash
        resp_complex = client.post("/api/chat", json={
            "message": "消費税減税におけるインフレ率と金利への波及効果の数理モデル分析",
            "routing_mode": "auto"
        })
        assert resp_complex.status_code == 200
        data_complex = resp_complex.json()
        assert data_complex["model"] == "gemini-3.8-flash"
        assert "routed_info" in data_complex
        assert data_complex["routed_info"]["model_id"] == "gemini-3.8-flash"

        # 2. 日常・共感クエリ ➔ gemini-3.5-flash-lite
        resp_casual = client.post("/api/chat", json={
            "message": "こんにちは！簡単でおいしいおにぎりの具を教えて",
            "routing_mode": "auto"
        })
        assert resp_casual.status_code == 200
        data_casual = resp_casual.json()
        assert data_casual["model"] == "gemini-3.5-flash-lite"
        assert "routed_info" in data_casual
        assert data_casual["routed_info"]["model_id"] == "gemini-3.5-flash-lite"
