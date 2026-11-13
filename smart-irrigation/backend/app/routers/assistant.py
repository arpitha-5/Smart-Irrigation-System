"""Assistant router for voice and chat agricultural advisory."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services import assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatQueryRequest(BaseModel):
    message: str = Field(..., description="Farmer's question or voice transcript")
    language: str = Field("en", description="Farmer's selected language: en, te, hi, ta, kn")
    field_id: Optional[str] = Field(None, description="Optional active field id")
    include_audio: bool = Field(True, description="Whether to generate native TTS audio")


class ChatQueryResponse(BaseModel):
    answer: str
    audio_base64: Optional[str] = None
    language: str
    field_id: Optional[str] = None
    field_name: Optional[str] = None
    crop_type: Optional[str] = None
    suggestions: List[str] = []


@router.get("/greeting")
def get_assistant_greeting(
    lang: str = Query("en", description="Language code: en, te, hi, ta, kn")
):
    """Returns localized greeting message and quick suggestion chips."""
    lang_clean = lang.strip().lower()[:2]
    greeting = assistant_service.GREETINGS.get(lang_clean, assistant_service.GREETINGS["en"])
    suggestions = assistant_service.SUGGESTIONS.get(lang_clean, assistant_service.SUGGESTIONS["en"])
    return {
        "greeting": greeting,
        "language": lang_clean,
        "suggestions": suggestions,
    }


@router.post("/chat", response_model=ChatQueryResponse)
async def chat_endpoint(
    payload: ChatQueryRequest,
    db: Session = Depends(get_db),
):
    """Process farmer's question and return intelligent answer with voice synthesis."""
    res = await assistant_service.answer_farmer_query(
        db=db,
        query=payload.message,
        target_language=payload.language,
        field_id=payload.field_id,
        include_audio=payload.include_audio,
    )
    return res
