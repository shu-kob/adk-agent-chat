import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model"] == "gemini-3.5-flash-lite"

def test_config_endpoint():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "model" in data
    assert "has_api_key" in data

def test_chat_endpoint_empty_message():
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400
    assert "Message content cannot be empty" in response.json()["detail"]

def test_chat_endpoint_success():
    payload = {
        "message": "Hello ADK Agent!",
        "session_id": "session_test_001",
        "user_id": "user_test"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["session_id"] == "session_test_001"
    assert data["model"] == "gemini-3.5-flash-lite"

def test_reset_session_endpoint():
    payload = {
        "session_id": "session_test_001",
        "user_id": "user_test"
    }
    response = client.post("/api/sessions/reset", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "session_cleared"
    assert data["session_id"] == "session_test_001"
