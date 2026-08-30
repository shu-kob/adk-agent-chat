"""
Unit Tests for ChatAgentManager Concurrent Non-blocking Execution (backend/tests/test_agent_concurrent_nonblocking.py)
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from agent import ChatAgentManager

class MockAsyncEvent:
    def __init__(self, text: str):
        self.text = text
        self.content = text

@pytest.fixture
def anyio_backend():
    return 'asyncio'

async def mock_async_event_stream(response_text: str, delay_sec: float = 0.05):
    """非同期ジェネレータのモック"""
    await asyncio.sleep(delay_sec)
    yield MockAsyncEvent(response_text)

@pytest.mark.anyio
async def test_agent_uses_run_async_and_handles_concurrent_requests():
    """
    ChatAgentManager が Runner.run_async を使用し、
    複数リクエストを並行にブロックせず処理できることを検証するテスト
    """
    manager = ChatAgentManager(allow_fallback=False)
    
    # ADK Runner のモック設定
    mock_runner = MagicMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session.return_value = MagicMock()
    
    # run_async が呼び出されると非同期ジェネレータを返すように設定
    mock_runner.run_async.side_effect = lambda user_id, session_id, new_message: mock_async_event_stream(
        f"Echo: {new_message}", delay_sec=0.1
    )
    
    manager.runner = mock_runner
    manager.session_service = mock_session_service

    start_t = time.time()

    # 3件のリクエストを同時に並行送信 (各0.1秒待機)
    tasks = [
        manager.generate_response(session_id="s1", prompt="Prompt 1"),
        manager.generate_response(session_id="s2", prompt="Prompt 2"),
        manager.generate_response(session_id="s3", prompt="Prompt 3"),
    ]

    responses = await asyncio.gather(*tasks)
    duration = time.time() - start_t

    # 1. 応答内容の検証
    assert responses == ["Echo: Prompt 1", "Echo: Prompt 2", "Echo: Prompt 3"]
    assert manager.last_execution_path == "adk"

    # 2. run_async が呼び出されたことの検証 (run ではない)
    assert mock_runner.run_async.call_count == 3

    # 3. ノンブロッキング並行実行の検証 (直列だと 0.3s 以上、並行なら 0.25s 未満)
    assert duration < 0.25
