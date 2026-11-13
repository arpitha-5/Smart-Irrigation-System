"""Tests for the AgriPulse AI Voice & Chat Assistant router and service."""
import pytest
from unittest.mock import AsyncMock, patch


def test_assistant_greeting_endpoint(client):
    """Verify greeting and suggestion chips for all 5 languages."""
    for lang in ["en", "te", "hi", "ta", "kn"]:
        response = client.get(f"/assistant/greeting?lang={lang}")
        assert response.status_code == 200
        data = response.json()
        assert "greeting" in data
        assert len(data["greeting"]) > 5
        assert "suggestions" in data
        assert len(data["suggestions"]) >= 3
        assert data["language"] == lang


@pytest.mark.anyio
async def test_assistant_chat_endpoint_water_query(client, monkeypatch):
    """Verify assistant answers irrigation/water questions with contextual telemetry."""
    # Mock external translation and TTS to run 100% offline
    from app.services import sarvam_service
    async def mock_translate(text, target_language, source_language="en"):
        return {"translated_text": f"[{target_language}] {text}", "is_fallback": True}
    async def mock_tts(text, target_language, speaker=None):
        return {"audio_base64": "UklGRlgRAgBXQVZF", "fallback": False}

    monkeypatch.setattr(sarvam_service, "translate_text", mock_translate)
    monkeypatch.setattr(sarvam_service, "text_to_speech", mock_tts)

    payload = {
        "message": "When should I irrigate my crops and how much water is needed?",
        "language": "en",
        "include_audio": False,
    }
    response = client.post("/assistant/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert ("irrigate" in data["answer"].lower() or "water" in data["answer"].lower() or "soil" in data["answer"].lower() or "field" in data["answer"].lower())
    assert data["language"] == "en"
    assert len(data["suggestions"]) >= 3


@pytest.mark.anyio
async def test_assistant_chat_endpoint_multilingual(client, monkeypatch):
    """Verify assistant handles queries in Indic languages (Telugu, Hindi)."""
    from app.services import sarvam_service
    async def mock_translate(text, target_language, source_language="en"):
        return {"translated_text": f"[{target_language}] Translated advice", "is_fallback": True}
    async def mock_tts(text, target_language, speaker=None):
        return {"audio_base64": "UklGRlgRAgBXQVZF", "fallback": False}

    monkeypatch.setattr(sarvam_service, "translate_text", mock_translate)
    monkeypatch.setattr(sarvam_service, "text_to_speech", mock_tts)

    for lang, query in [
        ("te", "ఈ రోజు నా పొలానికి నీరు పెట్టాలా?"),
        ("hi", "क्या आज मुझे अपने खेत में सिंचाई करनी चाहिए?"),
    ]:
        payload = {
            "message": query,
            "language": lang,
            "include_audio": True,
        }
        response = client.post("/assistant/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 5
        assert data["language"] == lang
        assert data["audio_base64"] == "UklGRlgRAgBXQVZF"
