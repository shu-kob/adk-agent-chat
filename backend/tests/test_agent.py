import pytest
import asyncio
from agent import ChatAgentManager

def test_agent_manager_init():
    manager = ChatAgentManager(model_name="gemini-3.5-flash-lite")
    assert manager.model_name == "gemini-3.5-flash-lite"

def test_get_or_create_session():
    async def run():
        manager = ChatAgentManager(model_name="gemini-3.5-flash-lite")
        session = await manager.get_or_create_session(session_id="test_session_123", user_id="test_user")
        assert session is not None or manager.session_service is None
    asyncio.run(run())

def test_clear_session():
    async def run():
        manager = ChatAgentManager(model_name="gemini-3.5-flash-lite")
        success = await manager.clear_session(session_id="test_session_123", user_id="test_user")
        assert success is True
    asyncio.run(run())

def test_generate_response_without_api_key(monkeypatch):
    async def run():
        monkeypatch.setattr("config.GOOGLE_API_KEY", "")
        monkeypatch.setattr("config.USE_VERTEXAI", False)
        manager = ChatAgentManager(model_name="gemini-3.5-flash-lite")
        response = await manager.generate_response(session_id="test_s1", prompt="Hello")
        assert "Authentication missing" in response or "API key is missing" in response or "Error" in response
    asyncio.run(run())
