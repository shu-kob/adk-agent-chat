import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from agent import ChatAgentManager

def test_agent_manager_allow_fallback_default():
    manager = ChatAgentManager(model_name="gemini-3.5-flash-lite")
    assert manager.allow_fallback is True

def test_agent_manager_disallow_fallback():
    manager = ChatAgentManager(model_name="gemini-3.5-flash-lite", allow_fallback=False)
    assert manager.allow_fallback is False

def test_fallback_disabled_raises_on_adk_error():
    async def run():
        manager = ChatAgentManager(model_name="gemini-3.5-flash-lite", allow_fallback=False)
        # Mock runner to raise an exception
        manager.runner = MagicMock()
        manager.runner.run_async = MagicMock(side_effect=RuntimeError("ADK Runner Internal Error"))
        manager.runner.run = MagicMock(side_effect=RuntimeError("ADK Runner Internal Error"))
        manager.session_service = MagicMock()
        manager.session_service.get_session = MagicMock(return_value=None)
        manager.session_service.create_session = MagicMock(return_value=MagicMock())

        with patch("agent.ADK_AVAILABLE", True), patch("config.GOOGLE_API_KEY", "dummy_key"):
            with pytest.raises(RuntimeError) as exc_info:
                await manager.generate_response(session_id="test_s", prompt="Hello")
            assert "ADK Runner Internal Error" in str(exc_info.value)
    asyncio.run(run())

def test_fallback_enabled_catches_adk_and_falls_back():
    async def run():
        manager = ChatAgentManager(model_name="gemini-3.5-flash-lite", allow_fallback=True)
        # Mock runner to raise an exception
        manager.runner = MagicMock()
        manager.runner.run_async = MagicMock(side_effect=RuntimeError("ADK Runner Error"))
        manager.runner.run = MagicMock(side_effect=RuntimeError("ADK Runner Error"))
        manager.session_service = MagicMock()
        manager.session_service.get_session = MagicMock(return_value=None)
        manager.session_service.create_session = MagicMock(return_value=MagicMock())

        with patch("agent.ADK_AVAILABLE", True), \
             patch("agent.GENAI_AVAILABLE", True), \
             patch("config.GOOGLE_API_KEY", "dummy_key"), \
             patch("google.genai.Client") as mock_client_cls:
            
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = "Fallback Response"
            mock_client.models.generate_content.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            resp = await manager.generate_response(session_id="test_s", prompt="Hello")
            assert resp == "Fallback Response"
            assert manager.last_execution_path == "genai_sdk_fallback"
    asyncio.run(run())
