"""
Unit Tests for Retry Mechanism with Exponential Backoff and Throttling (backend/tests/test_eval_retry_and_throttling.py)
"""

import pytest
import time
from unittest.mock import MagicMock
from eval.runner import execute_call_with_retry, is_retryable_error

class DummyResourceExhausted(Exception):
    """429 RESOURCE_EXHAUSTED のモック例外"""
    pass

class DummyInvalidArgument(Exception):
    """400 InvalidArgument のモック例外 (リトライ対象外)"""
    pass

def test_is_retryable_error():
    assert is_retryable_error(DummyResourceExhausted("429 Resource has been exhausted")) is True
    assert is_retryable_error(TimeoutError("Generation timed out")) is True
    assert is_retryable_error(ConnectionError("Connection aborted")) is True
    assert is_retryable_error(DummyInvalidArgument("400 Invalid argument")) is False
    assert is_retryable_error(ValueError("Invalid JSON")) is False

def test_execute_call_with_retry_succeeds_after_429():
    mock_func = MagicMock()
    # 1回目と2回目は429、3回目で成功
    mock_func.side_effect = [
        DummyResourceExhausted("429 ResourceExhausted"),
        DummyResourceExhausted("429 ResourceExhausted"),
        ("Success Output", 10, 20)
    ]

    start_t = time.time()
    result, retry_count = execute_call_with_retry(
        call_fn=mock_func,
        max_retries=3,
        base_delay_sec=0.01,
        backoff_factor=2.0
    )

    assert result == ("Success Output", 10, 20)
    assert retry_count == 2
    assert mock_func.call_count == 3

def test_execute_call_with_retry_fails_fast_on_non_retryable():
    mock_func = MagicMock()
    mock_func.side_effect = DummyInvalidArgument("400 Invalid argument")

    with pytest.raises(DummyInvalidArgument):
        execute_call_with_retry(
            call_fn=mock_func,
            max_retries=3,
            base_delay_sec=0.01
        )

    # リトライせず1回で失敗
    assert mock_func.call_count == 1
