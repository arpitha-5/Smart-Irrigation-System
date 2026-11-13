"""Sarvam AI service for Indic language dynamic translation, Text-to-Speech (TTS), and Speech-to-Text (STT).

Supported Indian languages:
- te: Telugu (తెలుగు) - te-IN
- hi: Hindi (हिन्दी) - hi-IN
- ta: Tamil (தமிழ்) - ta-IN
- kn: Kannada (ಕನ್ನಡ) - kn-IN
- en: English - en-IN

Handles graceful fallback when offline or if SARVAM_API_KEY is not configured.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import get_settings

log = logging.getLogger("irrigation.sarvam")

# Mapping short codes to Sarvam BCP-47 language codes
SARVAM_LANG_MAP: Dict[str, str] = {
    "te": "te-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "kn": "kn-IN",
    "en": "en-IN",
}

REVERSE_LANG_MAP: Dict[str, str] = {v: k for k, v in SARVAM_LANG_MAP.items()}

# Domain fallback glossary for agricultural recommendations & alerts (offline / no API key)
FALLBACK_PHRASES: Dict[str, Dict[str, str]] = {
    "te": {
        "IRRIGATE": "నీరు పెట్టండి",
        "IRRIGATE_IMMEDIATELY": "వెంటనే నీరు పెట్టండి",
        "IRRIGATE_LIGHT": "స్వల్పంగా నీరు పెట్టండి",
        "MAINTAIN_MONITORING": "పర్యవేక్షణ కొనసాగించండి",
        "DEFER_DUE_TO_RAIN": "వర్షం కారణంగా వాయిదా వేయండి",
        "NO_IRRIGATION_NEEDED": "నీటిపారుదల అవసరం లేదు",
        "WITHHELD": "నిలిపివేయబడింది",
        "HIGH": "అధిక ప్రాధాన్యత",
        "MODERATE": "మధ్యస్థం",
        "LOW": "తక్కువ",
        "NONE": "ఏదీ లేదు",
        "Drought Emergency": "తీవ్రమైన కరువు అత్యవసర పరిస్థితి",
        "Drought Risk": "కరువు ముప్పు",
        "Overwatering Risk": "అధిక నీటి ముప్పు",
        "Sensor reading is old": "సెన్సార్ పఠనం పాతది",
        "No soil-moisture reading": "నేల తేమ రీడింగ్ అందుబాటులో లేదు",
        "Irrigation decision withheld": "నీటిపారుదల నిర్ణయం తాత్కాలికంగా నిలిపివేయబడింది",
        "Irrigation deferred for rain": "వర్ష సూచన కారణంగా నీటిపారుదల వాయిదా పడింది",
    },
    "hi": {
        "IRRIGATE": "सिंचाई करें",
        "IRRIGATE_IMMEDIATELY": "तुरंत सिंचाई करें",
        "IRRIGATE_LIGHT": "हल्की सिंचाई करें",
        "MAINTAIN_MONITORING": "निगरानी जारी रखें",
        "DEFER_DUE_TO_RAIN": "बारिश के कारण स्थगित करें",
        "NO_IRRIGATION_NEEDED": "सिंचाई की आवश्यकता नहीं है",
        "WITHHELD": "रोका गया",
        "HIGH": "उच्च प्राथमिकता",
        "MODERATE": "मध्यम",
        "LOW": "कम",
        "NONE": "कोई नहीं",
        "Drought Emergency": "गंभीर सूखा आपातकाल",
        "Drought Risk": "सूखे का जोखिम",
        "Overwatering Risk": "अत्यधिक सिंचाई का जोखिम",
        "Sensor reading is old": "सेंसर डेटा पुराना है",
        "No soil-moisture reading": "मिट्टी की नमी का कोई डेटा नहीं",
        "Irrigation decision withheld": "सिंचाई निर्णय स्थगित रखा गया",
        "Irrigation deferred for rain": "बारिश के पूर्वानुमान के कारण सिंचाई स्थगित",
    },
    "ta": {
        "IRRIGATE": "பாசனம் செய்யவும்",
        "IRRIGATE_IMMEDIATELY": "உடனடியாக நீர் பாய்ச்சவும்",
        "IRRIGATE_LIGHT": "லேசான நீர்ப்பாசனம் செய்யவும்",
        "MAINTAIN_MONITORING": "தொடர்ந்து கண்காணிக்கவும்",
        "DEFER_DUE_TO_RAIN": "மழை காரணமாக ஒத்திவைக்கவும்",
        "NO_IRRIGATION_NEEDED": "நீர்ப்பாசனம் தேவையில்லை",
        "WITHHELD": "நிறுத்தி வைக்கப்பட்டது",
        "HIGH": "அதிக முன்னுரிமை",
        "MODERATE": "நடுத்தர",
        "LOW": "குறைந்த",
        "NONE": "எதுவுமில்லை",
        "Drought Emergency": "வறட்சி அவசரநிலை",
        "Drought Risk": "வறட்சி ஆபத்து",
        "Overwatering Risk": "அதிக நீர் தேக்க அபாயம்",
        "Sensor reading is old": "சென்சார் வாசிப்பு பழையது",
        "No soil-moisture reading": "மண் ஈரப்பத தகவல் இல்லை",
        "Irrigation decision withheld": "பாசன முடிவு நிறுத்தி வைக்கப்பட்டுள்ளது",
        "Irrigation deferred for rain": "மழை காரணமாக பாசனம் ஒத்திவைக்கப்பட்டது",
    },
    "kn": {
        "IRRIGATE": "ನೀರಾವರಿ ಮಾಡಿ",
        "IRRIGATE_IMMEDIATELY": "ತಕ್ಷಣ ನೀರಾವರಿ ಮಾಡಿ",
        "IRRIGATE_LIGHT": "ಸ್ವಲ್ಪ ನೀರುಣಿಸಿ",
        "MAINTAIN_MONITORING": "ಮೇಲ್ವಿಚಾರಣೆ ಮುಂದುವರಿಸಿ",
        "DEFER_DUE_TO_RAIN": "ಮಳೆಯ ಕಾರಣ ಮುಂದೂಡಿ",
        "NO_IRRIGATION_NEEDED": "ನೀರಾವರಿ ಅಗತ್ಯವಿಲ್ಲ",
        "WITHHELD": "ತಡೆಹಿಡಿಯಲಾಗಿದೆ",
        "HIGH": "ಹೆಚ್ಚಿನ ಆದ್ಯತೆ",
        "MODERATE": "ಮಧ್ಯಮ",
        "LOW": "ಕಡಿಮೆ",
        "NONE": "ಯಾವುದೂ ಇಲ್ಲ",
        "Drought Emergency": "ತೀವ್ರ ಬರಗಾಲದ ತುರ್ತು ಪರಿಸ್ಥಿತಿ",
        "Drought Risk": "ಬರಗಾಲದ ಅಪಾಯ",
        "Overwatering Risk": "ಹೆಚ್ಚು ನೀರಾವರಿ ಅಪಾಯ",
        "Sensor reading is old": "ಸಂವೇದಕ ರೀಡಿಂಗ್ ಹಳೆಯದಾಗಿದೆ",
        "No soil-moisture reading": "ಮಣ್ಣಿನ ತೇವಾಂಶ ಮಾಹಿತಿ ಇಲ್ಲ",
        "Irrigation decision withheld": "ನೀರಾವರಿ ನಿರ್ಧಾರವನ್ನು ತಡೆಹಿಡಿಯಲಾಗಿದೆ",
        "Irrigation deferred for rain": "ಮಳೆಯ ಮುನ್ಸೂಚನೆಯಿಂದ ನೀರಾವರಿ ಮುಂದೂಡಲಾಗಿದೆ",
    },
}


def normalize_lang_code(lang: str) -> str:
    """Map 'te' or 'te-IN' to short code 'te'."""
    clean = lang.strip().lower()
    if clean in SARVAM_LANG_MAP:
        return clean
    if clean in REVERSE_LANG_MAP:
        return REVERSE_LANG_MAP[clean]
    for k in SARVAM_LANG_MAP:
        if clean.startswith(k):
            return k
    return "en"


def to_sarvam_lang(lang: str) -> str:
    """Map 'te' or 'te-IN' to Sarvam BCP-47 code 'te-IN'."""
    short = normalize_lang_code(lang)
    return SARVAM_LANG_MAP.get(short, "en-IN")


# In-memory translation cache to avoid duplicate remote API calls
_TRANSLATION_CACHE: Dict[tuple[str, str], str] = {}


async def translate_text(
    text: str,
    target_language: str,
    source_language: str = "en",
) -> Dict[str, Any]:
    """Translate text dynamically using Sarvam AI translation API with offline fallback."""
    if not text or not text.strip():
        return {
            "translated_text": text,
            "source_language": source_language,
            "target_language": target_language,
            "is_fallback": False,
        }

    target_short = normalize_lang_code(target_language)
    source_short = normalize_lang_code(source_language)

    # If same language, no translation needed
    if target_short == source_short:
        return {
            "translated_text": text,
            "source_language": source_language,
            "target_language": target_language,
            "is_fallback": False,
        }

    clean_text = text.strip()
    cache_key = (clean_text, target_short)
    if cache_key in _TRANSLATION_CACHE:
        return {
            "translated_text": _TRANSLATION_CACHE[cache_key],
            "source_language": source_short,
            "target_language": target_short,
            "is_fallback": False,
        }

    settings = get_settings()
    target_sarvam = to_sarvam_lang(target_short)
    source_sarvam = to_sarvam_lang(source_short)

    if settings.sarvam_configured and settings.sarvam_api_key:
        url = f"{settings.sarvam_base_url.rstrip('/')}/translate"
        headers = {
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "input": clean_text,
            "source_language_code": source_sarvam,
            "target_language_code": target_sarvam,
            "model": settings.sarvam_translate_model,
        }

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    translated = data.get("translated_text", "")
                    if translated:
                        _TRANSLATION_CACHE[cache_key] = translated
                        return {
                            "translated_text": translated,
                            "source_language": source_sarvam,
                            "target_language": target_sarvam,
                            "is_fallback": False,
                            "model": settings.sarvam_translate_model,
                        }
                log.warning("Sarvam translate API error status %s: %s", res.status_code, res.text)
        except Exception as exc:
            log.warning("Sarvam translate request failed (%s): %s", type(exc).__name__, exc)

    # Fallback mechanism
    glossary = FALLBACK_PHRASES.get(target_short, {})
    if clean_text in glossary:
        fallback_val = glossary[clean_text]
        _TRANSLATION_CACHE[cache_key] = fallback_val
        return {
            "translated_text": fallback_val,
            "source_language": source_short,
            "target_language": target_short,
            "is_fallback": True,
        }

    # Partial phrase substitution for fallback
    translated_fallback = clean_text
    for eng, trans in glossary.items():
        if eng in translated_fallback:
            translated_fallback = translated_fallback.replace(eng, trans)

    _TRANSLATION_CACHE[cache_key] = translated_fallback
    return {
        "translated_text": translated_fallback,
        "source_language": source_short,
        "target_language": target_short,
        "is_fallback": True,
        "notice": "Translation generated via domain dictionary (Sarvam AI API key not configured or offline).",
    }


async def translate_batch(
    texts: List[str],
    target_language: str,
    source_language: str = "en",
) -> List[str]:
    """Translate a list of strings."""
    results = []
    for t in texts:
        if not t:
            results.append("")
            continue
        res = await translate_text(t, target_language, source_language)
        results.append(res.get("translated_text", t))
    return results


async def translate_recommendation(
    rec_dict: Dict[str, Any],
    target_language: str,
) -> Dict[str, Any]:
    """Translate dynamic strings inside an irrigation recommendation response concurrently."""
    target_short = normalize_lang_code(target_language)
    if target_short == "en":
        return rec_dict

    out = dict(rec_dict)

    try:
        # Translate core fields in parallel
        async def _safe_trans(text: Optional[str]) -> str:
            if not text:
                return ""
            try:
                res = await translate_text(text, target_language)
                return res.get("translated_text", text)
            except Exception:
                return text

        reason_fut = _safe_trans(out.get("reason"))
        action_fut = _safe_trans(out.get("action"))
        urgency_fut = _safe_trans(out.get("urgency"))
        limitations_fut = _safe_trans(out.get("limitations"))
        sched_note_fut = _safe_trans(out.get("scheduling_note"))

        # Wait for all core translations concurrently with a 4.0s timeout
        (
            out["translated_reason"],
            out["translated_action"],
            out["translated_urgency"],
            out["translated_limitations"],
            out["translated_scheduling_note"],
        ) = await asyncio.wait_for(
            asyncio.gather(
                reason_fut,
                action_fut,
                urgency_fut,
                limitations_fut,
                sched_note_fut,
            ),
            timeout=4.5,
        )

        # Translate irrigation schedule details if present
        schedule = out.get("irrigation_schedule")
        if schedule and isinstance(schedule, dict):
            trans_sched = dict(schedule)
            if schedule.get("reasons"):
                trans_sched["translated_reasons"] = await translate_batch(schedule["reasons"], target_language)
            if schedule.get("warnings"):
                trans_sched["translated_warnings"] = await translate_batch(schedule["warnings"], target_language)
            if schedule.get("assumptions"):
                trans_sched["translated_assumptions"] = await translate_batch(schedule["assumptions"], target_language)
            if schedule.get("disclaimer"):
                trans_sched["translated_disclaimer"] = await _safe_trans(schedule["disclaimer"])
            out["irrigation_schedule"] = trans_sched

        # Translate alerts if present
        alerts_data = out.get("alerts")
        if alerts_data and isinstance(alerts_data, dict):
            trans_alerts = dict(alerts_data)
            alert_items = alerts_data.get("alerts")
            if alert_items and isinstance(alert_items, list):
                new_items = []
                for a in alert_items:
                    item = dict(a)
                    if item.get("title"):
                        item["translated_title"] = await _safe_trans(item["title"])
                    if item.get("message"):
                        item["translated_message"] = await _safe_trans(item["message"])
                    if item.get("recommended_action"):
                        item["translated_recommended_action"] = await _safe_trans(item["recommended_action"])
                    new_items.append(item)
                trans_alerts["alerts"] = new_items
            out["alerts"] = trans_alerts
    except Exception as exc:
        log.warning("Fast concurrent translation timed out or error: %s; using original text", exc)
        out["translated_reason"] = out.get("reason")
        out["translated_action"] = out.get("action")
        out["translated_urgency"] = out.get("urgency")
        out["translated_limitations"] = out.get("limitations")
        out["translated_scheduling_note"] = out.get("scheduling_note")

    out["language"] = target_short
    out["language_code"] = to_sarvam_lang(target_short)
    return out


# Valid speakers for Sarvam bulbul:v3
SARVAM_PREFERRED_SPEAKERS: Dict[str, str] = {
    "te-IN": "kavitha",
    "hi-IN": "priya",
    "ta-IN": "vijay",
    "kn-IN": "aditya",
    "en-IN": "aditya",
}

VALID_BULBUL_SPEAKERS = {
    "aditya", "ritu", "ashutosh", "priya", "neha", "rahul", "pooja", "rohan", "simran",
    "kavya", "amit", "dev", "ishita", "shreya", "ratan", "varun", "manan", "sumit",
    "roopa", "kabir", "aayan", "shubh", "advait", "anand", "tanya", "tarun", "sunny",
    "mani", "gokul", "vijay", "shruti", "suhani", "mohit", "kavitha", "rehan", "soham",
    "rupali", "niharika"
}


async def text_to_speech(
    text: str,
    target_language: str,
    speaker: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert text to speech using Sarvam Bulbul model or return graceful client fallback instruction."""
    target_short = normalize_lang_code(target_language)
    target_sarvam = to_sarvam_lang(target_short)
    settings = get_settings()

    # Resolve speaker to a valid bulbul:v3 persona
    active_speaker = speaker if (speaker and speaker in VALID_BULBUL_SPEAKERS) else SARVAM_PREFERRED_SPEAKERS.get(target_sarvam, "aditya")

    if settings.sarvam_configured and settings.sarvam_api_key:
        url = f"{settings.sarvam_base_url.rstrip('/')}/text-to-speech"
        headers = {
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json",
        }
        # Sarvam Bulbul accepts inputs as an array of strings
        payload = {
            "inputs": [text[:1000]],
            "target_language_code": target_sarvam,
            "speaker": active_speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v3",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    audios = data.get("audios", [])
                    if audios and len(audios) > 0:
                        return {
                            "audio_base64": audios[0],
                            "target_language_code": target_sarvam,
                            "format": "wav",
                            "fallback": False,
                            "model": settings.sarvam_tts_model,
                        }
                log.warning("Sarvam TTS error status %s: %s", res.status_code, res.text)
        except Exception as exc:
            log.warning("Sarvam TTS request failed (%s): %s", type(exc).__name__, exc)

    # Return fallback instruction so frontend Web Speech API or audio synthesis can speak it
    return {
        "audio_base64": None,
        "target_language_code": target_sarvam,
        "format": None,
        "fallback": True,
        "text": text,
        "message": "Sarvam API not configured or offline; fallback to browser speech synthesis",
    }


async def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    language_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Transcribe audio using Sarvam Saaras model."""
    settings = get_settings()
    lang = to_sarvam_lang(language_code) if language_code else "unknown"

    if settings.sarvam_configured and settings.sarvam_api_key:
        url = f"{settings.sarvam_base_url.rstrip('/')}/speech-to-text"
        headers = {
            "api-subscription-key": settings.sarvam_api_key,
        }
        files = {
            "file": (filename, audio_bytes, "audio/wav"),
        }
        data = {
            "language_code": lang,
            "model": settings.sarvam_stt_model,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "transcript": data.get("transcript", ""),
                        "language_code": data.get("language_code", lang),
                        "fallback": False,
                    }
                log.warning("Sarvam STT error status %s: %s", res.status_code, res.text)
        except Exception as exc:
            log.warning("Sarvam STT request failed (%s): %s", type(exc).__name__, exc)

    return {
        "transcript": "",
        "language_code": lang,
        "fallback": True,
        "message": "Sarvam STT unavailable or API key not configured; using browser speech recognition",
    }


def get_service_status() -> Dict[str, Any]:
    """Return status of Sarvam AI integration."""
    settings = get_settings()
    return {
        "configured": settings.sarvam_configured,
        "base_url": settings.sarvam_base_url,
        "translate_model": settings.sarvam_translate_model,
        "tts_model": settings.sarvam_tts_model,
        "stt_model": settings.sarvam_stt_model,
        "supported_languages": [
            {"code": "te", "name": "Telugu", "native": "తెలుగు", "sarvam_code": "te-IN"},
            {"code": "hi", "name": "Hindi", "native": "हिन्दी", "sarvam_code": "hi-IN"},
            {"code": "ta", "name": "Tamil", "native": "தமிழ்", "sarvam_code": "ta-IN"},
            {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "sarvam_code": "kn-IN"},
            {"code": "en", "name": "English", "native": "English", "sarvam_code": "en-IN"},
        ],
    }
