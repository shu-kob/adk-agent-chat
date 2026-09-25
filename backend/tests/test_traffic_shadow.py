"""
Shadow Testing ユニットテスト (backend/tests/test_traffic_shadow.py)

書籍『Building Reliable AI Systems』Chapter 10.5「Shadow-testing new models」に基づく
オンライン・シャドウテスト機能の単体テスト。
"""

import os
import json
import pytest
import asyncio
import tempfile
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from eval.traffic.shadow import ShadowRunner
from eval.traffic.store import default_pii_masking_hook
from eval.traffic.diff_analyzer import compute_shadow_diff_metrics, generate_shadow_diff_report
from main import app


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def temp_shadow_log():
    """一時ファイルパスを提供するフィクスチャ"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_shadow_runner_initialization(temp_shadow_log):
    """初期化および各種設定値の検証"""
    runner = ShadowRunner(
        enabled=True,
        candidate_model_id="gemini-3.7-flash",
        sample_rate=0.5,
        timeout_sec=10.0,
        log_file_path=temp_shadow_log
    )
    assert runner.enabled is True
    assert runner.candidate_model_id == "gemini-3.7-flash"
    assert runner.sample_rate == 0.5
    assert runner.timeout_sec == 10.0
    assert runner.log_file_path == temp_shadow_log


def test_shadow_runner_should_sample():
    """サンプリング判定ロジックの検証"""
    # 1. 無効時
    runner_disabled = ShadowRunner(enabled=False, sample_rate=1.0)
    assert runner_disabled.should_sample() is False

    # 2. 有効かつ sample_rate=0.0
    runner_zero = ShadowRunner(enabled=True, sample_rate=0.0)
    assert runner_zero.should_sample() is False

    # 3. 有効かつ sample_rate=1.0
    runner_full = ShadowRunner(enabled=True, sample_rate=1.0)
    assert runner_full.should_sample() is True


@pytest.mark.anyio
async def test_shadow_runner_execute_success(temp_shadow_log):
    """モッククライアントを用いたシャドウテスト正常実行およびPIIマスキングの検証"""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Candidate AI output text with user@example.com"
    mock_resp.candidates = [MagicMock(finish_reason="STOP")]
    mock_resp.usage_metadata.prompt_token_count = 150
    mock_resp.usage_metadata.candidates_token_count = 80
    mock_client.models.generate_content.return_value = mock_resp

    runner = ShadowRunner(
        enabled=True,
        candidate_model_id="gemini-3.7-flash",
        sample_rate=1.0,
        log_file_path=temp_shadow_log,
        masking_hook=default_pii_masking_hook,
        client=mock_client
    )

    record = await runner.execute_shadow(
        session_id="session-123",
        input_text="My email is test@example.com and phone is 090-1234-5678",
        conversation_context=[{"role": "user", "text": "Call me at 03-1234-5678"}],
        production_output="Production answer with contact admin@example.com",
        production_model_id="gemini-3.5-flash-lite",
        production_latency_ms=450
    )

    # 戻り値の検証
    assert record["session_id"] == "session-123"
    assert record["input_text"] == "My email is [EMAIL] and phone is [PHONE]"
    assert record["conversation_context"][0]["text"] == "Call me at [PHONE]"
    assert record["production"]["output_text"] == "Production answer with contact [EMAIL]"
    assert record["production"]["latency_ms"] == 450
    assert record["candidate"]["output_text"] == "Candidate AI output text with [EMAIL]"
    assert record["candidate"]["prompt_tokens"] == 150
    assert record["candidate"]["candidate_tokens"] == 80
    assert record["candidate"]["status"] == "success"
    assert record["candidate"]["error_message"] is None

    # ファイル永続化の検証
    loaded = runner.load_shadow_records()
    assert len(loaded) == 1
    assert loaded[0]["shadow_id"] == record["shadow_id"]


@pytest.mark.anyio
async def test_shadow_runner_execute_error_isolated(temp_shadow_log):
    """候補モデル呼び出しで例外が発生しても本番に波及せずエラーレコードとして記録されるかの検証"""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Candidate model quota exceeded")

    runner = ShadowRunner(
        enabled=True,
        candidate_model_id="gemini-3.1-pro-preview",
        sample_rate=1.0,
        log_file_path=temp_shadow_log,
        client=mock_client
    )

    # 例外が外に漏れず完了すること
    record = await runner.execute_shadow(
        session_id="session-err",
        input_text="Hello",
        conversation_context=[],
        production_output="Normal production reply",
        production_model_id="gemini-3.5-flash-lite",
        production_latency_ms=300
    )

    assert record["candidate"]["status"] == "error"
    assert "Candidate model quota exceeded" in record["candidate"]["error_message"]

    # ログにも保存されていること
    loaded = runner.load_shadow_records()
    assert len(loaded) == 1
    assert loaded[0]["candidate"]["status"] == "error"


@pytest.mark.anyio
async def test_shadow_runner_schedule_async(temp_shadow_log):
    """schedule_shadow による非同期タスク発火の検証"""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Async shadow result"
    mock_resp.candidates = []
    mock_resp.usage_metadata = None
    mock_client.models.generate_content.return_value = mock_resp

    runner = ShadowRunner(
        enabled=True,
        candidate_model_id="gemini-2.5-flash",
        sample_rate=1.0,
        log_file_path=temp_shadow_log,
        client=mock_client
    )

    task = runner.schedule_shadow(
        session_id="session-async",
        input_text="Ping",
        conversation_context=[],
        production_output="Pong",
        production_model_id="gemini-3.5-flash-lite",
        production_latency_ms=200
    )

    assert isinstance(task, asyncio.Task)
    await task  # タスク完了を待機

    loaded = runner.load_shadow_records()
    assert len(loaded) == 1
    assert loaded[0]["candidate"]["output_text"] == "Async shadow result"


def test_shadow_diff_metrics_and_report():
    """シャドウ差分メトリクス計算とレポート生成の検証"""
    records = [
        {
            "shadow_id": "s1",
            "production": {"model_id": "gemini-3.5-flash-lite", "output_text": "Hello world", "latency_ms": 200},
            "candidate": {
                "model_id": "gemini-3.7-flash",
                "output_text": "Hello world",
                "latency_ms": 250,
                "prompt_tokens": 10,
                "candidate_tokens": 5,
                "cost_usd": 0.00001,
                "status": "success"
            }
        },
        {
            "shadow_id": "s2",
            "production": {"model_id": "gemini-3.5-flash-lite", "output_text": "Nice day", "latency_ms": 220},
            "candidate": {
                "model_id": "gemini-3.7-flash",
                "output_text": "Have a nice day!",
                "latency_ms": 300,
                "prompt_tokens": 12,
                "candidate_tokens": 8,
                "cost_usd": 0.000015,
                "status": "success"
            }
        },
        {
            "shadow_id": "s3",
            "production": {"model_id": "gemini-3.5-flash-lite", "output_text": "Error test", "latency_ms": 150},
            "candidate": {
                "model_id": "gemini-3.7-flash",
                "output_text": "",
                "latency_ms": 50,
                "status": "error",
                "error_message": "Timeout"
            }
        }
    ]

    metrics = compute_shadow_diff_metrics(records)
    assert metrics["total_records"] == 3
    assert metrics["success_count"] == 2
    assert metrics["error_count"] == 1
    assert metrics["exact_match_count"] == 1
    assert metrics["exact_match_ratio"] == 0.5  # 2件中1件一致
    assert metrics["avg_production_latency_ms"] == 210.0
    assert metrics["avg_candidate_latency_ms"] == 275.0

    report = generate_shadow_diff_report(metrics)
    assert "# 👥 Shadow Testing Evaluation Report (Chapter 10.5)" in report
    assert "gemini-3.5-flash-lite" in report
    assert "gemini-3.7-flash" in report
    assert "50.0%" in report


def test_fastapi_shadow_endpoints():
    """FastAPI のシャドウテスト関連エンドポイント疎通検証"""
    client = TestClient(app)

    # 1. /api/eval/shadow/status
    res_status = client.get("/api/eval/shadow/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert "enabled" in data_status
    assert "candidate_model_id" in data_status
    assert "sample_rate" in data_status

    # 2. /api/eval/shadow/report
    res_report = client.get("/api/eval/shadow/report")
    assert res_report.status_code == 200
    data_report = res_report.json()
    assert "metrics" in data_report
    assert "report_markdown" in data_report

    # 3. /api/eval/feedback/summary
    res_summary = client.get("/api/eval/feedback/summary")
    assert res_summary.status_code == 200
    assert "total_votes" in res_summary.json()

    # 4. /api/eval/batch/finops (Batch API 50% OFF report)
    res_batch = client.get("/api/eval/batch/finops")
    assert res_batch.status_code == 200
    batch_data = res_batch.json()
    assert "savings" in batch_data
    assert batch_data["savings"]["discount_percentage"] == "50.0%"
    assert "report_markdown" in batch_data


@pytest.mark.anyio
async def test_blind_ab_test_and_feedback_cycle(temp_shadow_log):
    """Side-by-Side ブラインド A/B テスト生成と投票フィードバック蓄積の検証"""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Candidate response for A/B"
    mock_resp.candidates = [MagicMock(finish_reason="STOP")]
    mock_resp.usage_metadata.prompt_token_count = 50
    mock_resp.usage_metadata.candidates_token_count = 30
    mock_client.models.generate_content.return_value = mock_resp

    runner = ShadowRunner(
        enabled=True,
        candidate_model_id="gemini-3.8-flash",
        sample_rate=1.0,
        log_file_path=temp_shadow_log,
        client=mock_client
    )

    ab_payload = await runner.run_blind_ab_test(
        session_id="session-ab-test",
        input_text="A/B question",
        conversation_context=[],
        production_output="Production response for A/B",
        production_model_id="gemini-3.7-flash",
        production_latency_ms=300
    )

    assert ab_payload is not None
    assert "ab_test_id" in ab_payload
    assert "choice_a" in ab_payload
    assert "choice_b" in ab_payload
    assert "mapping" in ab_payload
    assert "reveal_info" in ab_payload

    # ユーザー投票の送信
    record = runner.record_feedback(
        ab_test_id=ab_payload["ab_test_id"],
        session_id="session-ab-test",
        selected_choice="A",
        mapping=ab_payload["mapping"]
    )
    assert record["winner"] in ("production", "candidate")

    # サマリの取得
    summary = runner.get_feedback_summary()
    assert summary["total_votes"] >= 1
