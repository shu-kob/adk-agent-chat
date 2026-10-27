"""
モデル比較・選択機能ユニットテスト (backend/tests/test_model_selection.py)

【検証対象】
1. 標準モデルが gemini-3.8-flash であること
2. 比較対象モデル (3.5-flash-lite, 3.5-flash, 4-argon, random) の正規化と解決
3. run_blind_ab_test における指定モデルの適用と開示 (reveal_info)
4. /api/config エンドポイントの比較モデル一覧返却
5. /api/chat エンドポイントでの compare_model 連携
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

import config
from eval.traffic.shadow import (
    ShadowRunner,
    normalize_model_id,
    resolve_candidate_model
)
from main import app


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def test_default_standard_model_is_gemini_3_8_flash():
    """標準モデルが gemini-3.8-flash に設定されていることを検証"""
    assert config.GEMINI_MODEL == "gemini-3.8-flash"


def test_normalize_model_id():
    """エイリアスおよび短縮名が正式な識別子に正規化されることを検証"""
    assert normalize_model_id("3.5-flash-lite") == "gemini-3.5-flash-lite"
    assert normalize_model_id("3.5-flash") == "gemini-3.5-flash"
    assert normalize_model_id("4-argon") == "gemini-4-argon"
    assert normalize_model_id("gemini-4-argon") == "gemini-4-argon"
    assert normalize_model_id("random") == "random"


def test_resolve_candidate_model():
    """リクエストされた比較対象モデルの解決ロジックを検証"""
    # 1. 明示指定
    assert resolve_candidate_model("3.5-flash-lite", "gemini-3.8-flash") == "gemini-3.5-flash-lite"
    assert resolve_candidate_model("3.5-flash", "gemini-3.8-flash") == "gemini-3.5-flash"
    assert resolve_candidate_model("4-argon", "gemini-3.8-flash") == "gemini-4-argon"

    # 2. ランダムモード
    selected_samples = set()
    for _ in range(30):
        m = resolve_candidate_model("random", "gemini-3.8-flash")
        assert m in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-4-argon"]
        selected_samples.add(m)
    # 30回試行すれば3候補すべてが少なくとも1回は選ばれる可能性が極めて高い
    assert len(selected_samples) >= 2


@pytest.mark.anyio
async def test_run_blind_ab_test_with_selected_model():
    """run_blind_ab_test に候補モデルを明示指定した場合、reveal_info に正しく反映されることを検証"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "候補モデル gemini-4-argon の回答"
    mock_response.candidates = []
    mock_response.usage_metadata = MagicMock(prompt_token_count=30, candidates_token_count=20)
    mock_client.models.generate_content.return_value = mock_response

    runner = ShadowRunner(enabled=True, client=mock_client)

    result = await runner.run_blind_ab_test(
        session_id="test_sess_model_sel",
        input_text="こんにちは",
        conversation_context=[],
        production_output="標準モデルの回答",
        production_model_id="gemini-3.8-flash",
        production_latency_ms=120,
        candidate_model_id="gemini-4-argon"
    )

    assert result is not None
    assert "reveal_info" in result
    # A または B のどちらかが gemini-3.8-flash で、もう一方が gemini-4-argon
    models_in_reveal = {result["reveal_info"]["A"], result["reveal_info"]["B"]}
    assert models_in_reveal == {"gemini-3.8-flash", "gemini-4-argon"}


def test_api_config_returns_model_and_compare_models():
    """/api/config が標準モデル gemini-3.8-flash と比較対象モデル一覧を返却することを検証"""
    client = TestClient(app)
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()

    assert data["model"] == "gemini-3.8-flash"
    assert "compare_models" in data
    compare_ids = [opt["id"] for opt in data["compare_models"]]
    assert "random" in compare_ids
    assert "gemini-3.5-flash-lite" in compare_ids
    assert "gemini-3.5-flash" in compare_ids
    assert "gemini-4-argon" in compare_ids


def test_api_chat_accepts_compare_model(monkeypatch):
    """/api/chat エンドポイントが compare_model パラメータを受け入れて正常に応答することを検証"""
    from agent import agent_manager
    async def mock_generate_response(*args, **kwargs):
        return "モック応答です"
    monkeypatch.setattr(agent_manager, "generate_response", mock_generate_response)

    client = TestClient(app)
    response = client.post("/api/chat", json={
        "message": "モデル比較のテストです",
        "session_id": "test_sess_chat",
        "ab_test_mode": "off",
        "compare_model": "gemini-4-argon"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "モック応答です"
    assert data["model"] == "gemini-3.8-flash"
