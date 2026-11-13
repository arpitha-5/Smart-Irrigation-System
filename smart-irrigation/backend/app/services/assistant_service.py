"""AgriPulse AI Agricultural Voice & Chat Assistant Service.

Provides context-aware agronomic answers to farmers' questions (voice or text)
in Telugu, Hindi, Tamil, Kannada, and English, with synthesized voice output.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.sensor_reading import SensorReading
from app.models.weather_data import WeatherData
from app.services import sarvam_service
from app.services.irrigation_service import attach_irrigation_schedule, recommend_irrigation

log = logging.getLogger("irrigation.assistant")

# Multilingual default greetings and suggestion prompts
GREETINGS: Dict[str, str] = {
    "en": "Hello! I am your AgriPulse AI Farm Assistant. Ask me anything about your irrigation schedule, water requirements, soil moisture, or weather forecast.",
    "te": "నమస్కారం! నేను మీ అగ్రిపల్స్ AI వ్యవసాయ సహాయకుడిని. మీ నీటిపారుదల షెడ్యూల్, నీటి అవసరం, నేల తేమ లేదా వాతావరణం గురించి ఏదైనా అడగండి.",
    "hi": "नमस्ते! मैं आपका एग्रीपल्स AI कृषि सहायक हूँ। अपनी सिंचाई अनुसूची, पानी की आवश्यकता, मिट्टी की नमी या मौसम के बारे में कोई भी प्रश्न पूछें।",
    "ta": "வணக்கம்! நான் உங்கள் அக்ரிபல்ஸ் AI விவசாய உதவியாளர். நீர்ப்பாசன அட்டவணை, நீர்த்தேவை, மண் ஈரம் அல்லது வானிலை குறித்து எதையும் கேளுங்கள்.",
    "kn": "ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ ಅಗ್ರಿಪಲ್ಸ್ AI ಕೃಷಿ ಸಹಾಯಕ. ನಿಮ್ಮ ನೀರಾವರಿ ವೇಳಾಪಟ್ಟಿ, ನೀರಿನ ಅಗತ್ಯ, ಮಣ್ಣಿನ ತೇವಾಂಶ ಅಥವಾ ಹವಾಮಾನದ ಬಗ್ಗೆ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಕೇಳಿ.",
}

SUGGESTIONS: Dict[str, List[str]] = {
    "en": [
        "Should I irrigate my field today?",
        "What is the current soil moisture?",
        "What is the recommended irrigation start time and duration?",
        "Is there any rainfall forecasted?",
    ],
    "te": [
        "ఈ రోజు నా పొలానికి నీరు పెట్టాలా?",
        "ప్రస్తుతం నేలలో తేమ ఎంత ఉంది?",
        "నీరు పెట్టడానికి సరైన సమయం మరియు వ్యవధి ఎంత?",
        "రాబోయే 24 గంటల్లో వర్షం పడే అవకాశం ఉందా?",
    ],
    "hi": [
        "क्या आज मुझे अपने खेत में सिंचाई करनी चाहिए?",
        "वर्तमान में मिट्टी की नमी कितनी है?",
        "सिंचाई शुरू करने का अनुशंसित समय और अवधि क्या है?",
        "क्या आज बारिश होने की संभावना है?",
    ],
    "ta": [
        "இன்று நான் வயலுக்கு நீர் பாய்ச்ச வேண்டுமா?",
        "தற்போதைய மண் ஈரப்பதம் எவ்வளவு?",
        "பரிந்துரைக்கப்பட்ட நீர்ப்பாசன நேரம் மற்றும் கால அளவு என்ன?",
        "மழை பெய்ய வாய்ப்பு உள்ளதா?",
    ],
    "kn": [
        "ಇಂದು ನಾನು ನನ್ನ ಜಮೀನಿಗೆ ನೀರುಣಿಸಬೇಕೆ?",
        "ಪ್ರಸ್ತುತ ಮಣ್ಣಿನ ತೇವಾಂಶ ಎಷ್ಟಿದೆ?",
        "ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಾವರಿ ಸಮಯ ಮತ್ತು ಅವಧಿ ಎಷ್ಟು?",
        "ಮಳೆ ಬರುವ ಮುನ್ಸೂಚನೆ ಇದೆಯೇ?",
    ],
}


def _gather_farm_context(db: Session, field_id: Optional[str]) -> Dict[str, Any]:
    """Gathers live context for the field from sensors, crop type, weather, and ML advisory."""
    field: Optional[Field] = None
    if field_id:
        field = db.get(Field, field_id)
    if not field:
        field = db.scalars(select(Field).order_by(Field.name)).first()

    if not field:
        return {
            "has_field": False,
            "crop_type": "rice",
            "field_name": "Demo Field",
            "soil_moisture": 32.0,
            "temperature": 27.5,
            "humidity": 65.0,
            "rain_mm": 0.0,
            "area_ha": 1.0,
            "pump_flow_lpm": 250.0,
        }

    # Latest sensor reading
    reading = db.scalars(
        select(SensorReading)
        .where(SensorReading.field_id == field.field_id)
        .order_by(desc(SensorReading.timestamp))
    ).first()

    # Latest weather
    weather = db.scalars(
        select(WeatherData)
        .where(WeatherData.field_id == field.field_id)
        .order_by(desc(WeatherData.timestamp))
    ).first()

    soil_m = reading.soil_moisture if (reading and reading.soil_moisture is not None) else 30.0
    temp_c = (
        reading.temperature
        if (reading and reading.temperature is not None)
        else (weather.temperature_c if (weather and weather.temperature_c is not None) else 28.0)
    )
    humidity_pct = (
        reading.humidity
        if (reading and reading.humidity is not None)
        else (weather.humidity_pct if (weather and weather.humidity_pct is not None) else 65.0)
    )
    rain_mm = weather.rainfall_mm_24h if (weather and weather.rainfall_mm_24h is not None) else 0.0

    return {
        "has_field": True,
        "field_id": field.field_id,
        "field_name": field.name,
        "crop_type": field.crop_type or "rice",
        "soil_moisture": float(soil_m),
        "temperature": float(temp_c),
        "humidity": float(humidity_pct),
        "rain_mm": float(rain_mm),
        "area_ha": float(field.area_hectares or 1.0),
        "pump_flow_lpm": float(field.pump_flow_rate_lpm or 250.0),
    }


async def answer_farmer_query(
    db: Session,
    query: str,
    target_language: str = "en",
    field_id: Optional[str] = None,
    include_audio: bool = True,
) -> Dict[str, Any]:
    """Generates an intelligent contextual agronomic answer to the farmer's question."""
    lang_short = sarvam_service.normalize_lang_code(target_language)
    ctx = _gather_farm_context(db, field_id)
    q_lower = query.lower().strip()

    # Evaluate ML irrigation advisory for live context
    rec = recommend_irrigation(
        db=db,
        field_id=ctx.get("field_id"),
        crop_type=ctx["crop_type"],
        soil_moisture=ctx["soil_moisture"],
        temperature=ctx["temperature"],
        recent_rainfall_mm=ctx["rain_mm"],
    )
    if ctx.get("field_id"):
        rec = attach_irrigation_schedule(
            db=db,
            recommendation=rec,
            field_id=ctx.get("field_id"),
            flow_rate_lpm=ctx["pump_flow_lpm"],
        )

    action = rec.get("action", "MAINTAIN_MONITORING")
    sched = rec.get("scheduling_recommendation") or {}
    depth_mm = sched.get("ml_predicted_water_mm") or rec.get("recommended_water_mm") or 0.0
    vol_litres = sched.get("water_volume_litres") or round(depth_mm * ctx["area_ha"] * 10000, 1)
    duration_fmt = sched.get("duration_formatted") or "45 minutes"
    time_window = sched.get("recommended_time_window") or "06:00 - 08:30 (Morning)"
    field_name = ctx["field_name"]
    crop = ctx["crop_type"].capitalize()

    # Classify intent from question (multi-language keywords)
    is_water_query = any(k in q_lower for k in [
        "water", "irrigate", "irrigation", "when", "how much", "duration",
        "నీరు", "నీరు పెట్టాలా", "తడి", "ఎప్పుడు", "ఎంత",
        "पानी", "सिंचाई", "कब", "कितना",
        "தண்ணீர்", "பாசனம்", "எப்போது", "எவ்வளவு",
        "ನೀರು", "ನೀರಾವರಿ", "ಯಾವಾಗ", "ಎಷ್ಟು",
    ])
    is_moisture_query = any(k in q_lower for k in [
        "moisture", "dry", "wet", "soil", "status",
        "తేమ", "నేల", "భూమి",
        "नमी", "मिट्टी",
        "ஈரம்", "மண்",
        "ತೇವಾಂಶ", "ಮಣ್ಣು",
    ])
    is_weather_query = any(k in q_lower for k in [
        "weather", "rain", "temperature", "forecast", "sun", "hot", "cloud",
        "వర్షం", "వాతావరణం", "ఎండ", "ఉష్ణోగ్రత",
        "बारिश", "मौसम", "तापमान", "धूप",
        "மழை", "வானிலை", "வெப்பநிலை",
        "ಮಳೆ", "ಹವಾಮಾನ", "ತಾಪಮಾನ",
    ])
    is_crop_query = any(k in q_lower for k in [
        "crop", "pest", "fertilizer", "yield", "npk", "plant",
        "పంట", "పురుగు", "ఎరువు",
        "फसल", "कीट", "उर्वरक", "खाद",
        "பயிர்", "பூச்சி", "உரம்",
        "ಬೆಳೆ", "ಕೀಟ", "ಗೊಬ್ಬರ",
    ])

    # Formulate answer in English first, then accurately translate via Sarvam Indic
    english_answer: str = ""

    if is_water_query:
        if action.startswith("IRRIGATE"):
            english_answer = (
                f"For your field '{field_name}' growing {crop}: Yes, irrigation is required today. "
                f"The AI ML model predicts a water depth of {depth_mm:.1f} mm ({vol_litres:,.0f} Litres) "
                f"due to current soil moisture of {ctx['soil_moisture']:.1f}%. "
                f"Recommended irrigation window is {time_window} with an estimated pump runtime of {duration_fmt}."
            )
        elif action == "DEFER_DUE_TO_RAIN":
            english_answer = (
                f"For your field '{field_name}' growing {crop}: Irrigation is deferred because recent or upcoming rainfall "
                f"({ctx['rain_mm']:.1f} mm) is sufficient to replenish soil moisture naturally. Do not run the pump today to save power and water."
            )
        else:
            english_answer = (
                f"For your field '{field_name}' growing {crop}: No irrigation is needed at this time. "
                f"Current soil moisture ({ctx['soil_moisture']:.1f}%) is in the optimal range. "
                f"Continue monitoring via AgriPulse sensors."
            )
    elif is_moisture_query:
        status_desc = "critical / dry" if ctx["soil_moisture"] < 22 else ("optimal" if ctx["soil_moisture"] < 50 else "high / wet")
        english_answer = (
            f"The latest telemetry for field '{field_name}' indicates soil moisture at {ctx['soil_moisture']:.1f}%, "
            f"which is considered {status_desc} for {crop}. "
            f"Soil temperature is {ctx['temperature']:.1f}°C and relative air humidity is {ctx['humidity']:.1f}%."
        )
    elif is_weather_query:
        rain_text = f"{ctx['rain_mm']:.1f} mm recorded" if ctx['rain_mm'] > 0 else "no significant rainfall expected in the immediate 24-hour window"
        english_answer = (
            f"Current weather at '{field_name}': Ambient temperature is {ctx['temperature']:.1f}°C, "
            f"humidity is {ctx['humidity']:.1f}%, and {rain_text}. "
            f"{'Avoid mid-day irrigation due to high heat evaporation.' if ctx['temperature'] > 30 else 'Conditions are favorable for crop uptake.'}"
        )
    elif is_crop_query:
        english_answer = (
            f"For your {crop} field in '{field_name}': Maintain balanced nitrogen and phosphorus levels, "
            f"and avoid excess standing water during root development. Consult our Crop Suitability module "
            f"for tailored NPK nutrient recommendations."
        )
    else:
        # Comprehensive farm overview
        rec_text = f"irrigation of {depth_mm:.1f} mm is recommended ({time_window})" if action.startswith("IRRIGATE") else "soil moisture is optimal and no watering is required"
        english_answer = (
            f"Here is your farm summary for '{field_name}' ({crop}): Current soil moisture is {ctx['soil_moisture']:.1f}%, "
            f"ambient temperature is {ctx['temperature']:.1f}°C, and {rec_text}."
        )

    # Translate answer into farmer's selected language
    final_answer = english_answer
    if lang_short != "en":
        try:
            import asyncio
            trans_res = await asyncio.wait_for(
                sarvam_service.translate_text(
                    text=english_answer,
                    target_language=lang_short,
                    source_language="en",
                ),
                timeout=4.5,
            )
            final_answer = trans_res.get("translated_text", english_answer)
        except Exception as exc:
            log.warning("Assistant translation fallback: %s", exc)

    # Generate speech audio using Sarvam Bulbul:v3 with timeout
    audio_base64: Optional[str] = None
    if include_audio:
        try:
            import asyncio
            tts_res = await asyncio.wait_for(
                sarvam_service.text_to_speech(
                    text=final_answer[:450],
                    target_language=lang_short,
                ),
                timeout=6.5,
            )
            if tts_res and not tts_res.get("fallback"):
                audio_base64 = tts_res.get("audio_base64")
        except Exception as exc:
            log.warning("Assistant TTS generation fallback: %s", exc)

    return {
        "answer": final_answer,
        "audio_base64": audio_base64,
        "language": lang_short,
        "field_id": ctx.get("field_id"),
        "field_name": field_name,
        "crop_type": crop,
        "suggestions": SUGGESTIONS.get(lang_short, SUGGESTIONS["en"]),
    }
