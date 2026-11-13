"""Sarvam AI router for multilingual farmer assistance."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.services import sarvam_service

router = APIRouter(prefix="/sarvam", tags=["sarvam"])


class TranslateRequest(BaseModel):
    text: str = Field(..., description="Text to translate")
    target_language: str = Field(..., description="Target language code: te, hi, ta, kn, en")
    source_language: str = Field("en", description="Source language code: en, te, hi, ta, kn")


class RecommendationTranslateRequest(BaseModel):
    recommendation: Dict[str, Any] = Field(..., description="Irrigation recommendation response object")
    target_language: str = Field(..., description="Target language code: te, hi, ta, kn, en")


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=1500, description="Text to convert into speech")
    target_language: str = Field(..., description="Language code: te, hi, ta, kn, en")
    speaker: Optional[str] = Field("meera", description="Voice persona, e.g., meera")


@router.get("/status")
def get_sarvam_status():
    """Check Sarvam AI integration readiness and supported Indian languages."""
    return sarvam_service.get_service_status()


@router.post("/translate")
async def translate_text_endpoint(payload: TranslateRequest):
    """Translate dynamic text into Telugu, Hindi, Tamil, Kannada, or English."""
    return await sarvam_service.translate_text(
        text=payload.text,
        target_language=payload.target_language,
        source_language=payload.source_language,
    )


@router.post("/translate-recommendation")
async def translate_recommendation_endpoint(payload: RecommendationTranslateRequest):
    """Translate all dynamic text inside an irrigation recommendation."""
    return await sarvam_service.translate_recommendation(
        rec_dict=payload.recommendation,
        target_language=payload.target_language,
    )


@router.post("/text-to-speech")
async def text_to_speech_endpoint(payload: TTSRequest):
    """Synthesize speech audio for recommendations and alerts."""
    return await sarvam_service.text_to_speech(
        text=payload.text,
        target_language=payload.target_language,
        speaker=payload.speaker or "meera",
    )


@router.post("/speech-to-text")
async def speech_to_text_endpoint(
    file: UploadFile = File(...),
    language_code: Optional[str] = Form(None),
):
    """Transcribe voice query in farmer's selected language using Sarvam Saaras."""
    content = await file.read()
    return await sarvam_service.speech_to_text(
        audio_bytes=content,
        filename=file.filename or "recording.wav",
        language_code=language_code,
    )


class Base64STTRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio bytes (WAV/WEBM/MP3)")
    language_code: Optional[str] = Field(None, description="Language code: te, hi, ta, kn, en, or BCP-47")
    filename: Optional[str] = Field("recording.wav", description="Filename hint")


@router.post("/speech-to-text-base64")
async def speech_to_text_base64_endpoint(payload: Base64STTRequest):
    """Transcribe base64 encoded audio in farmer's selected language."""
    import base64
    clean_b64 = payload.audio_base64
    if "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]
    raw_bytes = base64.b64decode(clean_b64)
    return await sarvam_service.speech_to_text(
        audio_bytes=raw_bytes,
        filename=payload.filename or "recording.wav",
        language_code=payload.language_code,
    )

