import pytest
from unittest.mock import MagicMock
from eval.precheck import validate_model_availability

def test_validate_model_availability_all_succeed():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "pong"
    mock_client.models.generate_content.return_value = mock_resp

    models = ["gemini-2.5-flash", "gemini-2.5-pro"]
    valid_models, skipped_models = validate_model_availability(mock_client, models)

    assert valid_models == ["gemini-2.5-flash", "gemini-2.5-pro"]
    assert skipped_models == []

def test_validate_model_availability_skips_failed_model():
    mock_client = MagicMock()

    def side_effect(model, contents, config=None):
        if model == "gemini-invalid-model":
            raise RuntimeError("404 Model Not Found")
        mock_resp = MagicMock()
        mock_resp.text = "pong"
        return mock_resp

    mock_client.models.generate_content.side_effect = side_effect

    models = ["gemini-2.5-flash", "gemini-invalid-model"]
    valid_models, skipped_models = validate_model_availability(mock_client, models)

    assert valid_models == ["gemini-2.5-flash"]
    assert len(skipped_models) == 1
    assert skipped_models[0]["model_id"] == "gemini-invalid-model"
    assert "404 Model Not Found" in skipped_models[0]["error"]
