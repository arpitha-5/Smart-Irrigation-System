"""Unit and integration tests for Sarvam AI dynamic language features."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import sarvam_service

UNCONFIGURED_SETTINGS = type("MockSettings", (), {
    "sarvam_configured": False,
    "sarvam_api_key": None,
    "sarvam_base_url": "https://api.sarvam.ai",
    "sarvam_translate_model": "sarvam-translate:v1",
    "sarvam_tts_model": "bulbul:v1",
    "sarvam_stt_model": "saaras:v2",
})()


def test_sarvam_status(client):
    """Verify /sarvam/status lists all 5 required languages."""
    response = client.get("/sarvam/status")
    assert response.status_code == 200
    data = response.json()
    assert "supported_languages" in data
    codes = [l["code"] for l in data["supported_languages"]]
    assert set(codes) == {"te", "hi", "ta", "kn", "en"}


def test_sarvam_all_five_languages_translation_fallback(client):
    """Verify each of the 5 languages can translate actions and alerts without errors."""
    with patch("app.services.sarvam_service.get_settings", return_value=UNCONFIGURED_SETTINGS):
        for lang in ["te", "hi", "ta", "kn", "en"]:
            response = client.post(
                "/sarvam/translate",
                json={
                    "text": "IRRIGATE_IMMEDIATELY",
                    "target_language": lang,
                    "source_language": "en",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "translated_text" in data
            assert len(data["translated_text"]) > 0


def test_sarvam_all_five_languages_tts(client):
    """Verify TTS request returns valid response for all 5 languages."""
    with patch("app.services.sarvam_service.get_settings", return_value=UNCONFIGURED_SETTINGS):
        for lang in ["te", "hi", "ta", "kn", "en"]:
            response = client.post(
                "/sarvam/text-to-speech",
                json={
                    "text": "Irrigation advisory notification",
                    "target_language": lang,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "target_language_code" in data
            assert data["target_language_code"].endswith("-IN")


def test_sarvam_translate_mock_api(client):
    """Verify Sarvam API is invoked properly when configured."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"translated_text": "तुरंत सिंचाई करें"}
        mock_post.return_value = mock_response

        mock_settings = type("MockSettings", (), {
            "sarvam_configured": True,
            "sarvam_api_key": "test-key-12345",
            "sarvam_base_url": "https://api.sarvam.ai",
            "sarvam_translate_model": "sarvam-translate:v1",
        })()
        with patch("app.services.sarvam_service.get_settings", return_value=mock_settings):
            response = client.post(
                "/sarvam/translate",
                json={
                    "text": "Irrigate immediately",
                    "target_language": "hi",
                    "source_language": "en",
                },
            )
            assert response.status_code == 200
            assert response.json()["translated_text"] == "तुरंत सिंचाई करें"


def test_sarvam_tts_mock_api(client):
    """Verify Sarvam TTS API handles base64 audio return."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"audios": ["UklGRiQAAABXQVZFZm10"]}
        mock_post.return_value = mock_response

        mock_settings = type("MockSettings", (), {
            "sarvam_configured": True,
            "sarvam_api_key": "test-key-12345",
            "sarvam_base_url": "https://api.sarvam.ai",
            "sarvam_tts_model": "bulbul:v1",
        })()
        with patch("app.services.sarvam_service.get_settings", return_value=mock_settings):
            response = client.post(
                "/sarvam/text-to-speech",
                json={
                    "text": "నీరు పెట్టండి",
                    "target_language": "te",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["audio_base64"] == "UklGRiQAAABXQVZFZm10"
            assert data["fallback"] is False


def test_sarvam_stt_base64(client):
    """Verify Base64 STT endpoint handles audio bytes gracefully."""
    import base64
    dummy_wav_b64 = base64.b64encode(b"RIFF....WAVEfmt ").decode("ascii")

    with patch("app.services.sarvam_service.get_settings", return_value=UNCONFIGURED_SETTINGS):
        response = client.post(
            "/sarvam/speech-to-text-base64",
            json={
                "audio_base64": dummy_wav_b64,
                "language_code": "te",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "transcript" in data
        assert data["fallback"] is True


def test_translate_recommendation_all_languages(client):
    """Verify recommendation object translation for Telugu, Tamil, and Hindi."""
    rec = {
        "action": "IRRIGATE_IMMEDIATELY",
        "urgency": "HIGH",
        "reason": "Soil moisture is critically low.",
        "recommended_water_mm": 15.0,
        "recommendation_engine": "ml_model",
        "sensor_freshness": "fresh",
        "limitations": "Advisory only.",
        "irrigation_schedule": {
            "action": "IRRIGATE",
            "reasons": ["Rainfall is not expected", "Critical soil dryness"],
            "warnings": [],
            "assumptions": ["Drip system assumed"],
            "disclaimer": "Verify on site.",
        },
        "alerts": {
            "alerts": [
                {
                    "title": "Drought Emergency",
                    "message": "Crop at risk",
                    "recommended_action": "IRRIGATE",
                }
            ]
        },
    }

    with patch("app.services.sarvam_service.get_settings", return_value=UNCONFIGURED_SETTINGS):
        for lang in ["te", "ta", "hi", "kn"]:
            response = client.post(
                "/sarvam/translate-recommendation",
                json={"recommendation": rec, "target_language": lang},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == lang
            assert "translated_action" in data
            assert "translated_urgency" in data
            assert "alerts" in data
            assert len(data["alerts"]["alerts"]) > 0
            assert "translated_title" in data["alerts"]["alerts"][0]
