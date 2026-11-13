"""Report generation service: generates professional multilingual PDF and CSV reports.

Extracts actual database records for fields, farmers, crops, sensor telemetry,
weather observations, actual irrigation logs, and the existing ML prediction & schedule.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crop import Crop
from app.models.farmer import Farmer
from app.models.field import Field
from app.models.irrigation_log import IrrigationLog
from app.models.sensor_reading import SensorReading
from app.models.weather_data import WeatherData
from app.services.irrigation_service import attach_irrigation_schedule, recommend_irrigation

log = logging.getLogger("irrigation.report.service")

# ── Font setup for Indic Unicode rendering ──────────────────────────────────────────────────────────

_FONT_REGISTERED = False
_INDIC_FONT_NAME = "Helvetica"


def _init_pdf_fonts() -> str:
    global _FONT_REGISTERED, _INDIC_FONT_NAME
    if _FONT_REGISTERED:
        return _INDIC_FONT_NAME

    # Look for Windows Nirmala / Arial Unicode or Linux Indic fonts
    candidates = [
        ("Nirmala", "C:\\Windows\\Fonts\\Nirmala.ttc", 0),
        ("ArialUnicode", "C:\\Windows\\Fonts\\ARIALUNI.ttf", None),
        ("FreeSans", "/usr/share/fonts/truetype/freefont/FreeSans.ttf", None),
        ("Lohit", "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf", None),
    ]

    for name, path, sub_idx in candidates:
        if os.path.isfile(path):
            try:
                if sub_idx is not None:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=sub_idx))
                else:
                    pdfmetrics.registerFont(TTFont(name, path))
                _INDIC_FONT_NAME = name
                log.info("Registered ReportLab Unicode font: %s from %s", name, path)
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not register font %s: %s", path, exc)

    _FONT_REGISTERED = True
    return _INDIC_FONT_NAME


# ── Multilingual localized strings ──────────────────────────────────────────────────────────────────

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Smart Irrigation & Field Water Management Report",
        "subtitle": "Agronomic Intelligence, Telemetry Audit & Irrigation Scheduling",
        "generated_on": "Generated On",
        "farmer_profile": "Farmer Profile",
        "field_profile": "Field & Crop Details",
        "farmer_name": "Farmer Name",
        "farmer_id": "Farmer ID",
        "phone": "Contact Phone",
        "field_id": "Field ID",
        "field_name": "Field Name",
        "area": "Field Area",
        "crop": "Crop Type",
        "stage": "Growth Stage",
        "flow_rate": "Pump Flow Rate",
        "ml_scheduling_header": "AI ML Irrigation Prediction & Scheduling Recommendation",
        "ml_water_depth": "Predicted Water Requirement",
        "ml_water_volume": "Total Water Volume",
        "rec_date": "Recommended Irrigation Date",
        "rec_window": "Recommended Time Window",
        "est_duration": "Estimated Duration",
        "scheduling_reason": "Advisory Scheduling Reason",
        "disclaimer_label": "Advisory Disclaimer",
        "disclaimer_text": "This schedule is an advisory recommendation for the farmer. Not an automatic pump actuation.",
        "sensor_history_header": "Sensor Telemetry & Soil Moisture History",
        "weather_history_header": "Recent Weather Observations",
        "irrigation_history_header": "Actual Recorded Irrigation Events",
        "alerts_header": "Active Alerts & Agronomic Observations",
        "no_sensor_data": "No sensor readings recorded for this field in the selected period.",
        "no_weather_data": "No weather observations recorded for this field in the selected period.",
        "no_irrigation_data": "No actual irrigation events logged for this field in the selected period.",
        "no_alerts": "No active emergency or warning alerts. Field telemetry is within safe operating thresholds.",
        "col_timestamp": "Timestamp (UTC)",
        "col_sensor": "Sensor ID",
        "col_moisture": "Soil Moisture (%)",
        "col_temp": "Temp (°C)",
        "col_humidity": "Humidity (%)",
        "col_rain": "Rain (mm)",
        "col_wind": "Wind (m/s)",
        "col_condition": "Condition",
        "col_depth_applied": "Depth Applied (mm)",
        "col_volume_applied": "Volume (Litres)",
        "col_duration": "Duration",
        "col_source": "Source",
        "col_notes": "Notes",
        "not_configured": "Flow rate not configured",
        "none_advisory": "No irrigation needed",
    },
    "te": {
        "title": "స్మార్ట్ నీటిపారుదల & క్షేత్ర నివేదిక",
        "subtitle": "వ్యవసాయ మేధస్సు, సెన్సార్ డేటా & నీటిపారుదల షెడ్యూల్",
        "generated_on": "నివేదిక రూపొందించిన సమయం",
        "farmer_profile": "రైతు వివరాలు",
        "field_profile": "పొలం & పంట వివరాలు",
        "farmer_name": "రైతు పేరు",
        "farmer_id": "రైతు ఐడీ",
        "phone": "ఫోన్ నంబర్",
        "field_id": "పొలం ఐడీ",
        "field_name": "పొలం పేరు",
        "area": "పొలం వైశాల్యం",
        "crop": "పంట రకం",
        "stage": "పెరుగుదల దశ",
        "flow_rate": "మోటారు ప్రవాహ వేగం",
        "ml_scheduling_header": "కృత్రిమ మేధస్సు (AI ML) నీటిపారుదల అంచనా & షెడ్యూల్",
        "ml_water_depth": "అవసరమైన నీటి లోతు",
        "ml_water_volume": "మొత్తం నీటి పరిమాణం",
        "rec_date": "సిఫార్సు చేసిన తేదీ",
        "rec_window": "సిఫార్సు చేసిన సమయం",
        "est_duration": "అవసరమైన వ్యవధి",
        "scheduling_reason": "సలహా కారణం",
        "disclaimer_label": "రైతుకు సూచన",
        "disclaimer_text": "ఇది రైతుకు కేవలం సలహా మాత్రమే. ఆటోమేటిక్ పంప్ ఆపరేషన్ కాదు.",
        "sensor_history_header": "నేల తేమ & సెన్సార్ రీడింగుల చరిత్ర",
        "weather_history_header": "ఇటీవలి వాతావరణ వివరాలు",
        "irrigation_history_header": "గతంలో జరిగిన అసలు నీటిపారుదల రికార్డులు",
        "alerts_header": "హెచ్చరికలు & వ్యవసాయ సూచనలు",
        "no_sensor_data": "ఎంచుకున్న కాలంలో ఈ పొలానికి సంబంధించి సెన్సార్ రీడింగులు లేవు.",
        "no_weather_data": "ఎంచుకున్న కాలంలో వాతావరణ వివరాలు నమోదు కాలేదు.",
        "no_irrigation_data": "ఎంచుకున్న కాలంలో నీటిపారుదల రికార్డులు ఏవీ లేవు.",
        "no_alerts": "ప్రస్తుతం ఎటువంటి హెచ్చరికలు లేవు. నేల తేమ సాధారణంగా ఉంది.",
        "col_timestamp": "సమయం",
        "col_sensor": "సెన్సార్ ఐడీ",
        "col_moisture": "నేల తేమ (%)",
        "col_temp": "ఉష్ణోగ్రత (°C)",
        "col_humidity": "గాలి తేమ (%)",
        "col_rain": "వర్షం (mm)",
        "col_wind": "గాలి వేగం (m/s)",
        "col_condition": "వాతావరణం",
        "col_depth_applied": "నీటి లోతు (mm)",
        "col_volume_applied": "నీటి పరిమాణం (లీటర్లు)",
        "col_duration": "వ్యవధి",
        "col_source": "మూలం",
        "col_notes": "వివరాలు",
        "not_configured": "ప్రవాహ వేగం నమోదు చేయలేదు",
        "none_advisory": "ప్రస్తుతం నీరు అవసరం లేదు",
    },
    "hi": {
        "title": "स्मार्ट सिंचाई एवं खेत जल प्रबंधन रिपोर्ट",
        "subtitle": "कृषि बुद्धिमत्ता, सेंसर डेटा एवं अनुशंसित सिंचाई कार्यक्रम",
        "generated_on": "रिपोर्ट तैयार होने की तिथि",
        "farmer_profile": "किसान का विवरण",
        "field_profile": "खेत एवं फसल विवरण",
        "farmer_name": "किसान का नाम",
        "farmer_id": "किसान आईडी",
        "phone": "संपर्क फोन",
        "field_id": "खेत आईडी",
        "field_name": "खेत का नाम",
        "area": "खेत का क्षेत्रफल",
        "crop": "फसल का प्रकार",
        "stage": "विकास चरण",
        "flow_rate": "पंप प्रवाह दर",
        "ml_scheduling_header": "एआई एमएल सिंचाई पूर्वानुमान एवं अनुशंसित कार्यक्रम",
        "ml_water_depth": "आवश्यक जल स्तर",
        "ml_water_volume": "कुल जल मात्रा",
        "rec_date": "अनुशंसित सिंचाई तिथि",
        "rec_window": "अनुशंसित समय अंतराल",
        "est_duration": "अनुमानित समय",
        "scheduling_reason": "सलाह का कारण",
        "disclaimer_label": "कृषक सलाह",
        "disclaimer_text": "यह किसान के लिए एक अनुशंसित सलाह है। यह स्वचालित पंप संचालन नहीं है।",
        "sensor_history_header": "सेंसर मिट्टी की नमी का इतिहास",
        "weather_history_header": "मौसम की हालिया जानकारी",
        "irrigation_history_header": "वास्तविक सिंचाई का इतिहास",
        "alerts_header": "सक्रिय चेतावनियां एवं कृषि सलाह",
        "no_sensor_data": "इस अवधि में इस खेत के लिए कोई सेंसर रीडिंग उपलब्ध नहीं है।",
        "no_weather_data": "इस अवधि में मौसम का कोई डेटा उपलब्ध नहीं है।",
        "no_irrigation_data": "इस अवधि में कोई सिंचाई दर्ज नहीं की गई है।",
        "no_alerts": "कोई सक्रिय चेतावनी नहीं है। नमी का स्तर सामान्य है।",
        "col_timestamp": "समय",
        "col_sensor": "सेंसर आईडी",
        "col_moisture": "मिट्टी की नमी (%)",
        "col_temp": "तापमान (°C)",
        "col_humidity": "आर्द्रता (%)",
        "col_rain": "वर्षा (mm)",
        "col_wind": "हवा (m/s)",
        "col_condition": "मौसम",
        "col_depth_applied": "दी गई गहराई (mm)",
        "col_volume_applied": "मात्रा (लीटर)",
        "col_duration": "अवधि",
        "col_source": "स्रोत",
        "col_notes": "टिप्पणी",
        "not_configured": "प्रवाह दर कॉन्फ़िगर नहीं है",
        "none_advisory": "सिंचाई की आवश्यकता नहीं है",
    },
    "ta": {
        "title": "ஸ்மார்ட் பாசனம் மற்றும் வயல் நீர் மேலாண்மை அறிக்கை",
        "subtitle": "வேளாண் நுண்ணறிவு, சென்சார் தரவு மற்றும் பாசன அட்டவணை",
        "generated_on": "அறிக்கை உருவாக்கப்பட்ட தேதி",
        "farmer_profile": "விவசாயி விவரங்கள்",
        "field_profile": "வயல் மற்றும் பயிர் விவரங்கள்",
        "farmer_name": "விவசாயி பெயர்",
        "farmer_id": "விவசாயி ஐடி",
        "phone": "தொலைபேசி",
        "field_id": "வயல் ஐடி",
        "field_name": "வயல் பெயர்",
        "area": "வயல் பரப்பளவு",
        "crop": "பயிர் வகை",
        "stage": "வளர்ச்சி நிலை",
        "flow_rate": "பம்பு ஓட்ட விகிதம்",
        "ml_scheduling_header": "AI ML பாசன கணிப்பு மற்றும் பரிந்துரைக்கப்பட்ட அட்டவணை",
        "ml_water_depth": "தேவையான நீர் அளவு",
        "ml_water_volume": "மொத்த நீர் அளவு",
        "rec_date": "பரிந்துரைக்கப்பட்ட தேதி",
        "rec_window": "பரிந்துரைக்கப்பட்ட நேரம்",
        "est_duration": "மதிப்பிடப்பட்ட காலம்",
        "scheduling_reason": "பரிந்துரைக்கான காரணம்",
        "disclaimer_label": "விவசாயிக்கு ஆலோசனை",
        "disclaimer_text": "இது விவசாயிக்கான வழிகாட்டுதல் மட்டுமே. தானியங்கி பாசனம் அல்ல.",
        "sensor_history_header": "மண் ஈரப்பதம் மற்றும் சென்சார் வரலாறு",
        "weather_history_header": "சமீபத்திய வானிலை தகவல்கள்",
        "irrigation_history_header": "உண்மையான பாசன வரலாறு",
        "alerts_header": "எச்சரிக்கைகள் மற்றும் வேளாண் அவதானிப்புகள்",
        "no_sensor_data": "தேர்ந்தெடுக்கப்பட்ட காலத்தில் சென்சார் தரவு இல்லை.",
        "no_weather_data": "தேர்ந்தெடுக்கப்பட்ட காலத்தில் வானிலை தரவு இல்லை.",
        "no_irrigation_data": "தேர்ந்தெடுக்கப்பட்ட காலத்தில் பாசன பதிவுகள் இல்லை.",
        "no_alerts": "எச்சரிக்கைகள் எதுவும் இல்லை. மண் ஈரப்பதம் சீராக உள்ளது.",
        "col_timestamp": "நேரம்",
        "col_sensor": "சென்சார் ஐடி",
        "col_moisture": "மண் ஈரப்பதம் (%)",
        "col_temp": "வெப்பநிலை (°C)",
        "col_humidity": "ஈரப்பதம் (%)",
        "col_rain": "மழை (mm)",
        "col_wind": "காற்று (m/s)",
        "col_condition": "வானிலை",
        "col_depth_applied": "பாய்ச்சப்பட்ட ஆழம் (mm)",
        "col_volume_applied": "அளவு (லிட்டர்)",
        "col_duration": "காலம்",
        "col_source": "மூலம்",
        "col_notes": "குறிப்புகள்",
        "not_configured": "ஓட்ட விகிதம் உள்ளிடப்படவில்லை",
        "none_advisory": "பாசனம் தேவையில்லை",
    },
    "kn": {
        "title": "ಸ್ಮಾರ್ಟ್ ನೀರಾವರಿ ಮತ್ತು ಜಮೀನಿನ ನೀರು ನಿರ್ವಹಣಾ ವರದಿ",
        "subtitle": "ಕೃಷಿ ಬುದ್ಧಿಮತ್ತೆ, ಸಂವೇದಕ ಡೇಟಾ ಮತ್ತು ನೀರಾವರಿ ವೇಳಾಪಟ್ಟಿ",
        "generated_on": "ವರದಿ ತಯಾರಿಸಿದ ದಿನಾಂಕ",
        "farmer_profile": "ರೈತರ ವಿವರಗಳು",
        "field_profile": "ಜಮೀನು ಮತ್ತು ಬೆಳೆ ವಿವರಗಳು",
        "farmer_name": "ರೈತರ ಹೆಸರು",
        "farmer_id": "ರೈತರ ಐಡಿ",
        "phone": "ದೂರವಾಣಿ ಸಂಖ್ಯೆ",
        "field_id": "ಜಮೀನಿನ ಐಡಿ",
        "field_name": "ಜಮೀನಿನ ಹೆಸರು",
        "area": "ವಿಸ್ತೀರ್ಣ",
        "crop": "ಬೆಳೆಯ ವಿಧ",
        "stage": "ಬೆಳವಣಿಗೆಯ ಹಂತ",
        "flow_rate": "ಪಂಪ್ ಹರಿವಿನ ಪ್ರಮಾಣ",
        "ml_scheduling_header": "AI ML ನೀರಾವರಿ ಮುನ್ಸೂಚನೆ ಮತ್ತು ಶಿಫಾರಸು ಮಾಡಿದ ವೇಳಾಪಟ್ಟಿ",
        "ml_water_depth": "ಅಗತ್ಯವಿರುವ ನೀರಿನ ಆಳ",
        "ml_water_volume": "ಒಟ್ಟು ನೀರಿನ ಪ್ರಮಾಣ",
        "rec_date": "ಶಿಫಾರಸು ಮಾಡಿದ ದಿನಾಂಕ",
        "rec_window": "ಶಿಫಾರಸು ಮಾಡಿದ ಸಮಯ",
        "est_duration": "ಅಂದಾಜು ಅವಧಿ",
        "scheduling_reason": "ಶಿಫಾರಸಿನ ವಿವರಣೆ",
        "disclaimer_label": "ರೈತರಿಗೆ ಸಲಹೆ",
        "disclaimer_text": "ಇದು ಕೇವಲ ರೈತರಿಗೆ ಮಾರ್ಗದರ್ಶನವಾಗಿದೆ. ಸ್ವಯಂಚಾಲಿತ ಪಂಪ್ ಕಾರ್ಯಾಚರಣೆ ಅಲ್ಲ.",
        "sensor_history_header": "ಮಣ್ಣಿನ ತೇವಾಂಶ ಮತ್ತು ಸಂವೇದಕ ಇತಿಹಾಸ",
        "weather_history_header": "ಇತ್ತೀಚಿನ ಹವಾಮಾನ ಮಾಹಿತಿ",
        "irrigation_history_header": "ನೈಜ ನೀರಾವರಿ ದಾಖಲೆಗಳ ಇತಿಹಾಸ",
        "alerts_header": "ಎಚ್ಚರಿಕೆಗಳು ಮತ್ತು ಕೃಷಿ ವೀಕ್ಷಣೆಗಳು",
        "no_sensor_data": "ಆಯ್ಕೆಮಾಡಿದ ಅವಧಿಯಲ್ಲಿ ಯಾವುದೇ ಸಂವೇದಕ ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ.",
        "no_weather_data": "ಆಯ್ಕೆಮಾಡಿದ ಅವಧಿಯಲ್ಲಿ ಯಾವುದೇ ಹವಾಮಾನ ಡೇಟಾ ಲಭ್ಯವಿಲ್ಲ.",
        "no_irrigation_data": "ಆಯ್ಕೆಮಾಡಿದ ಅವಧಿಯಲ್ಲಿ ಯಾವುದೇ ನೀರಾವರಿ ದಾಖಲಾಗಿಲ್ಲ.",
        "no_alerts": "ಯಾವುದೇ ಸಕ್ರಿಯ ಎಚ್ಚರಿಕೆಗಳಿಲ್ಲ. ಮಣ್ಣಿನ ತೇವಾಂಶವು ಸಹಜ ಸ್ಥಿತಿಯಲ್ಲಿದೆ.",
        "col_timestamp": "ಸಮಯ",
        "col_sensor": "ಸಂವೇದಕ ಐಡಿ",
        "col_moisture": "ಮಣ್ಣಿನ ತೇವಾಂಶ (%)",
        "col_temp": "ತಾಪಮಾನ (°C)",
        "col_humidity": "ಆರ್ದ್ರತೆ (%)",
        "col_rain": "ಮಳೆ (mm)",
        "col_wind": "ಗಾಳಿಯ ವೇಗ (m/s)",
        "col_condition": "ಹವಾಮಾನ",
        "col_depth_applied": "ನೀರಿನ ಆಳ (mm)",
        "col_volume_applied": "ಪ್ರಮಾಣ (ಲೀಟರ್)",
        "col_duration": "ಅವಧಿ",
        "col_source": "ಮೂಲ",
        "col_notes": "ಟಿಪ್ಪಣಿಗಳು",
        "not_configured": "ಹರಿವಿನ ಪ್ರಮಾಣ ನಿಗದಿಪಡಿಸಿಲ್ಲ",
        "none_advisory": "ನೀರಾವರಿ ಅಗತ್ಯವಿಲ್ಲ",
    },
}


def _get_lang_dict(lang: str) -> Dict[str, str]:
    code = (lang or "en").strip().lower()
    if code.startswith("te"):
        return TRANSLATIONS["te"]
    if code.startswith("hi"):
        return TRANSLATIONS["hi"]
    if code.startswith("ta"):
        return TRANSLATIONS["ta"]
    if code.startswith("kn"):
        return TRANSLATIONS["kn"]
    return TRANSLATIONS["en"]


# ── Aggregate Report Data ────────────────────────────────────────────────────────────────────────────

def gather_report_data(
    db: Session,
    field_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """Queries actual database rows for a field. Never fabricates sensor or irrigation data."""
    field = db.get(Field, field_id)
    if not field:
        raise ValueError(f"Field '{field_id}' does not exist.")

    farmer = field.farmer or db.get(Farmer, field.farmer_id)
    crop = db.scalar(
        select(Crop).where(Crop.field_id == field_id).order_by(Crop.created_at.desc()).limit(1)
    )

    # Sensor readings (actual only)
    sensor_stmt = select(SensorReading).where(SensorReading.field_id == field_id)
    if start_date:
        sensor_stmt = sensor_stmt.where(SensorReading.timestamp >= start_date)
    if end_date:
        sensor_stmt = sensor_stmt.where(SensorReading.timestamp <= end_date)
    sensor_stmt = sensor_stmt.order_by(SensorReading.timestamp.desc()).limit(50)
    sensors = db.scalars(sensor_stmt).all()

    # Weather records (actual only)
    weather_stmt = select(WeatherData).where(WeatherData.field_id == field_id)
    if start_date:
        weather_stmt = weather_stmt.where(WeatherData.timestamp >= start_date)
    if end_date:
        weather_stmt = weather_stmt.where(WeatherData.timestamp <= end_date)
    weather_stmt = weather_stmt.order_by(WeatherData.timestamp.desc()).limit(20)
    weather_records = db.scalars(weather_stmt).all()

    # Irrigation logs (actual only)
    irrig_stmt = select(IrrigationLog).where(IrrigationLog.field_id == field_id)
    if start_date:
        irrig_stmt = irrig_stmt.where(IrrigationLog.timestamp >= start_date)
    if end_date:
        irrig_stmt = irrig_stmt.where(IrrigationLog.timestamp <= end_date)
    irrig_stmt = irrig_stmt.order_by(IrrigationLog.timestamp.desc()).limit(20)
    irrigation_records = db.scalars(irrig_stmt).all()

    # Reuse existing ML prediction and scheduling without modification
    rec = recommend_irrigation(db=db, field_id=field_id)
    scheduled = attach_irrigation_schedule(
        db, rec, field_id, flow_rate_lpm=field.pump_flow_rate_lpm
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "lang": lang,
        "farmer": farmer,
        "field": field,
        "crop": crop,
        "sensors": sensors,
        "weather_records": weather_records,
        "irrigation_records": irrigation_records,
        "recommendation": scheduled,
        "start_date": start_date,
        "end_date": end_date,
    }


# ── PDF Generation ───────────────────────────────────────────────────────────────────────────────────

def generate_pdf_report(data: Dict[str, Any]) -> bytes:
    """Builds a PDF report in memory using ReportLab."""
    font_name = _init_pdf_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    L = _get_lang_dict(data.get("lang", "en"))
    field = data["field"]
    farmer = data["farmer"]
    crop = data["crop"]
    rec = data["recommendation"]
    sched_info = rec.get("scheduling_recommendation") or {}

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1B4D3E"),
        fontBold=True,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1B4D3E"),
        fontBold=True,
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        fontName=font_name,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    )
    body_bold = ParagraphStyle(
        "BodyBoldCustom",
        fontName=font_name,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
        fontBold=True,
    )
    card_text = ParagraphStyle(
        "CardText",
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph(f"AgriPulse AI — {L['title']}", title_style))
    gen_time_str = data["generated_at"].strftime("%Y-%m-%d %H:%M:%S UTC")
    date_filter_str = ""
    if data.get("start_date") or data.get("end_date"):
        s_str = data["start_date"].strftime("%Y-%m-%d") if data.get("start_date") else "Earliest"
        e_str = data["end_date"].strftime("%Y-%m-%d") if data.get("end_date") else "Latest"
        date_filter_str = f" | Period: {s_str} to {e_str}"
    story.append(
        Paragraph(
            f"{L['subtitle']} | {L['generated_on']}: {gen_time_str}{date_filter_str}",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1B4D3E"), spaceAfter=10))

    # 2. Farmer & Field Profile Table
    story.append(Paragraph(f"1. {L['farmer_profile']} & {L['field_profile']}", heading_style))

    farmer_name_val = getattr(farmer, "name", "N/A") if farmer else "N/A"
    farmer_id_val = getattr(farmer, "farmer_id", "N/A") if farmer else "N/A"
    farmer_phone_val = getattr(farmer, "phone", "N/A") if farmer else "N/A"
    field_id_val = field.field_id
    field_name_val = getattr(field, "name", field.field_id)
    area_val = f"{field.area_hectares} ha" if field.area_hectares else "N/A"
    crop_val = getattr(crop, "crop_type", field.crop_type) or "N/A"
    stage_val = getattr(crop, "growth_stage", "vegetative") or "vegetative"
    flow_rate_val = (
        f"{field.pump_flow_rate_lpm} L/min" if field.pump_flow_rate_lpm else L["not_configured"]
    )

    profile_data = [
        [
            Paragraph(f"<b>{L['farmer_name']}:</b>", body_style),
            Paragraph(str(farmer_name_val), body_style),
            Paragraph(f"<b>{L['field_id']}:</b>", body_style),
            Paragraph(str(field_id_val), body_style),
        ],
        [
            Paragraph(f"<b>{L['farmer_id']}:</b>", body_style),
            Paragraph(str(farmer_id_val), body_style),
            Paragraph(f"<b>{L['field_name']}:</b>", body_style),
            Paragraph(str(field_name_val), body_style),
        ],
        [
            Paragraph(f"<b>{L['phone']}:</b>", body_style),
            Paragraph(str(farmer_phone_val), body_style),
            Paragraph(f"<b>{L['area']}:</b>", body_style),
            Paragraph(str(area_val), body_style),
        ],
        [
            Paragraph(f"<b>{L['crop']}:</b>", body_style),
            Paragraph(str(crop_val), body_style),
            Paragraph(f"<b>{L['stage']}:</b>", body_style),
            Paragraph(str(stage_val).title(), body_style),
        ],
        [
            Paragraph(f"<b>{L['flow_rate']}:</b>", body_style),
            Paragraph(str(flow_rate_val), body_style),
            Paragraph("<b>Irrigation Method:</b>", body_style),
            Paragraph(str(getattr(field, "irrigation_method", "Drip") or "Drip").title(), body_style),
        ],
    ]
    t_profile = Table(profile_data, colWidths=[1.3 * inch, 2.3 * inch, 1.4 * inch, 2.2 * inch])
    t_profile.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_profile)
    story.append(Spacer(1, 12))

    # 3. AI ML Prediction & Irrigation Scheduling Box
    story.append(Paragraph(f"2. {L['ml_scheduling_header']}", heading_style))

    water_depth_val = sched_info.get("ml_predicted_water_mm", rec.get("recommended_water_mm", 0.0))
    vol_litres_val = sched_info.get("water_volume_litres")
    vol_str = f"{vol_litres_val:,.1f} Litres" if vol_litres_val is not None else "Not calculated (Field area required)"
    rec_date_val = sched_info.get("recommended_date") or L["none_advisory"]
    rec_window_val = sched_info.get("recommended_time_window") or L["none_advisory"]
    duration_val = sched_info.get("duration_formatted") or L["not_configured"]
    sched_reason = sched_info.get("reason") or rec.get("reason", "")
    engine_name = rec.get("recommendation_engine", "AI Two-Stage Gradient Boosting ML Model")

    sched_rows = [
        [
            Paragraph(f"<b>{L['ml_water_depth']}:</b>", card_text),
            Paragraph(f"<b>{water_depth_val} mm</b> (Gross applied water depth)", card_text),
        ],
        [
            Paragraph(f"<b>{L['ml_water_volume']}:</b>", card_text),
            Paragraph(f"{vol_str}", card_text),
        ],
        [
            Paragraph(f"<b>{L['rec_date']}:</b>", card_text),
            Paragraph(f"<b>{rec_date_val}</b>", card_text),
        ],
        [
            Paragraph(f"<b>{L['rec_window']}:</b>", card_text),
            Paragraph(f"<b>{rec_window_val}</b>", card_text),
        ],
        [
            Paragraph(f"<b>{L['est_duration']}:</b>", card_text),
            Paragraph(f"<b>{duration_val}</b>", card_text),
        ],
        [
            Paragraph(f"<b>{L['flow_rate']}:</b>", card_text),
            Paragraph(f"{flow_rate_val}", card_text),
        ],
        [
            Paragraph(f"<b>Predictive Engine:</b>", card_text),
            Paragraph(f"{engine_name}", card_text),
        ],
        [
            Paragraph(f"<b>{L['scheduling_reason']}:</b>", card_text),
            Paragraph(f"{sched_reason}", card_text),
        ],
        [
            Paragraph(f"<b>{L['disclaimer_label']}:</b>", card_text),
            Paragraph(f"<i>{L['disclaimer_text']}</i>", card_text),
        ],
    ]
    t_sched = Table(sched_rows, colWidths=[2.2 * inch, 5.0 * inch])
    t_sched.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBF7D0")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_sched)
    story.append(Spacer(1, 12))

    # 4. Actual Irrigation Records
    story.append(Paragraph(f"3. {L['irrigation_history_header']}", heading_style))
    irrig_rows = [
        [
            Paragraph(f"<b>{L['col_timestamp']}</b>", body_bold),
            Paragraph(f"<b>{L['col_depth_applied']}</b>", body_bold),
            Paragraph(f"<b>{L['col_volume_applied']}</b>", body_bold),
            Paragraph(f"<b>{L['col_duration']}</b>", body_bold),
            Paragraph(f"<b>{L['col_source']}</b>", body_bold),
            Paragraph(f"<b>{L['col_notes']}</b>", body_bold),
        ]
    ]
    if data["irrigation_records"]:
        for record in data["irrigation_records"]:
            ts_text = record.timestamp.strftime("%Y-%m-%d %H:%M") if record.timestamp else "N/A"
            dur_text = f"{record.duration_minutes:.0f} min" if record.duration_minutes else "N/A"
            notes_text = record.notes or "—"
            irrig_rows.append(
                [
                    Paragraph(ts_text, body_style),
                    Paragraph(f"{record.water_depth_mm:.1f} mm", body_style),
                    Paragraph(f"{record.water_volume_litres:,.0f} L", body_style),
                    Paragraph(dur_text, body_style),
                    Paragraph(record.source.replace("_", " ").title(), body_style),
                    Paragraph(notes_text, body_style),
                ]
            )
    else:
        irrig_rows.append([Paragraph(L["no_irrigation_data"], body_style), "", "", "", "", ""])

    t_irrig = Table(irrig_rows, colWidths=[1.3 * inch, 1.1 * inch, 1.3 * inch, 0.9 * inch, 1.1 * inch, 1.5 * inch])
    t_irrig.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    if not data["irrigation_records"]:
        t_irrig.setStyle(TableStyle([("SPAN", (0, 1), (-1, 1))]))
    story.append(t_irrig)
    story.append(Spacer(1, 12))

    # 5. Sensor Telemetry History
    story.append(Paragraph(f"4. {L['sensor_history_header']}", heading_style))
    sensor_rows = [
        [
            Paragraph(f"<b>{L['col_timestamp']}</b>", body_bold),
            Paragraph(f"<b>{L['col_sensor']}</b>", body_bold),
            Paragraph(f"<b>{L['col_moisture']}</b>", body_bold),
            Paragraph(f"<b>{L['col_temp']}</b>", body_bold),
            Paragraph("<b>Quality Status</b>", body_bold),
        ]
    ]
    if data["sensors"]:
        for s in data["sensors"][:15]:
            ts_text = s.timestamp.strftime("%Y-%m-%d %H:%M") if s.timestamp else "N/A"
            m_val = f"{s.soil_moisture:.1f}%" if s.soil_moisture is not None else (f"{s.value:.1f}%" if s.value is not None else "N/A")
            t_val = f"{s.temperature:.1f}°C" if s.temperature is not None else "N/A"
            q_status = (s.quality_status or "valid").capitalize()
            sensor_rows.append(
                [
                    Paragraph(ts_text, body_style),
                    Paragraph(s.sensor_id, body_style),
                    Paragraph(m_val, body_style),
                    Paragraph(t_val, body_style),
                    Paragraph(q_status, body_style),
                ]
            )
    else:
        sensor_rows.append([Paragraph(L["no_sensor_data"], body_style), "", "", "", ""])

    t_sensors = Table(sensor_rows, colWidths=[1.6 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch])
    t_sensors.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    if not data["sensors"]:
        t_sensors.setStyle(TableStyle([("SPAN", (0, 1), (-1, 1))]))
    story.append(t_sensors)
    story.append(Spacer(1, 12))

    # 6. Weather Observations
    story.append(Paragraph(f"5. {L['weather_history_header']}", heading_style))
    weather_rows = [
        [
            Paragraph(f"<b>{L['col_timestamp']}</b>", body_bold),
            Paragraph(f"<b>{L['col_temp']}</b>", body_bold),
            Paragraph(f"<b>{L['col_humidity']}</b>", body_bold),
            Paragraph(f"<b>{L['col_wind']}</b>", body_bold),
            Paragraph(f"<b>{L['col_rain']}</b>", body_bold),
            Paragraph(f"<b>{L['col_condition']}</b>", body_bold),
        ]
    ]
    if data["weather_records"]:
        for w in data["weather_records"][:10]:
            ts_text = w.timestamp.strftime("%Y-%m-%d %H:%M") if w.timestamp else "N/A"
            t_val = f"{w.temperature:.1f}°C" if w.temperature is not None else "N/A"
            h_val = f"{w.humidity:.0f}%" if w.humidity is not None else "N/A"
            w_val = f"{w.wind_speed:.1f} m/s" if w.wind_speed is not None else "N/A"
            r_val = f"{w.rainfall:.1f} mm" if w.rainfall is not None else "0.0 mm"
            cond_val = (w.condition or "Clear").title()
            weather_rows.append(
                [
                    Paragraph(ts_text, body_style),
                    Paragraph(t_val, body_style),
                    Paragraph(h_val, body_style),
                    Paragraph(w_val, body_style),
                    Paragraph(r_val, body_style),
                    Paragraph(cond_val, body_style),
                ]
            )
    else:
        weather_rows.append([Paragraph(L["no_weather_data"], body_style), "", "", "", "", ""])

    t_weather = Table(weather_rows, colWidths=[1.4 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 1.4 * inch])
    t_weather.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    if not data["weather_records"]:
        t_weather.setStyle(TableStyle([("SPAN", (0, 1), (-1, 1))]))
    story.append(t_weather)
    story.append(Spacer(1, 12))

    # 7. Active Alerts & Agronomic Advisory
    story.append(Paragraph(f"6. {L['alerts_header']}", heading_style))
    alerts_data = rec.get("alerts")
    alert_list = (alerts_data or {}).get("alerts", [])
    if alert_list:
        for a in alert_list:
            lvl = a.get("level", "INFO")
            msg = a.get("message", "")
            action_req = a.get("action_required", "")
            color_hex = "#DC2626" if lvl == "EMERGENCY" else ("#D97706" if lvl == "WARNING" else "#2563EB")
            p_text = f"<font color='{color_hex}'><b>[{lvl}]</b></font> {msg} <i>(Action: {action_req})</i>"
            story.append(Paragraph(p_text, body_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph(L["no_alerts"], body_style))

    doc.build(story)
    return buffer.getvalue()


# ── CSV Generation (UTF-8 BOM for Excel Compatibility) ──────────────────────────────────────────────

def generate_csv_report(data: Dict[str, Any]) -> str:
    """Generates clean CSV text formatted with UTF-8 BOM for Microsoft Excel."""
    L = _get_lang_dict(data.get("lang", "en"))
    field = data["field"]
    farmer = data["farmer"]
    crop = data["crop"]
    rec = data["recommendation"]
    sched_info = rec.get("scheduling_recommendation") or {}

    out = io.StringIO()
    # Write UTF-8 BOM
    out.write("\ufeff")
    writer = csv.writer(out)

    # Header section
    writer.writerow(["AGRIPULSE AI - SMART IRRIGATION FIELD REPORT"])
    writer.writerow(["Report Title", L["title"]])
    writer.writerow(["Generated At (UTC)", data["generated_at"].strftime("%Y-%m-%d %H:%M:%S")])
    if data.get("start_date") or data.get("end_date"):
        writer.writerow([
            "Filter Date Range",
            f"{data['start_date'].strftime('%Y-%m-%d') if data.get('start_date') else 'All'} to {data['end_date'].strftime('%Y-%m-%d') if data.get('end_date') else 'Latest'}"
        ])
    writer.writerow([])

    # Farmer & Field Details
    writer.writerow(["--- FARMER & FIELD PROFILE ---"])
    writer.writerow(["Field ID", field.field_id])
    writer.writerow(["Field Name", getattr(field, "name", field.field_id)])
    writer.writerow(["Farmer ID", getattr(farmer, "farmer_id", "N/A") if farmer else "N/A"])
    writer.writerow(["Farmer Name", getattr(farmer, "name", "N/A") if farmer else "N/A"])
    writer.writerow(["Contact Phone", getattr(farmer, "phone", "N/A") if farmer else "N/A"])
    writer.writerow(["Field Area (hectares)", field.area_hectares or "Not specified"])
    writer.writerow(["Crop Type", getattr(crop, "crop_type", field.crop_type) or "N/A"])
    writer.writerow(["Growth Stage", getattr(crop, "growth_stage", "vegetative") or "vegetative"])
    writer.writerow(["Configured Pump Flow Rate (LPM)", field.pump_flow_rate_lpm or "Not configured"])
    writer.writerow(["Irrigation Method", getattr(field, "irrigation_method", "Drip") or "Drip"])
    writer.writerow([])

    # AI ML Prediction & Schedule
    writer.writerow(["--- AI ML IRRIGATION PREDICTION & SCHEDULE ---"])
    writer.writerow(["ML Predicted Water Requirement (mm)", sched_info.get("ml_predicted_water_mm", rec.get("recommended_water_mm", 0.0))])
    writer.writerow(["Calculated Water Volume (Litres)", sched_info.get("water_volume_litres") or "N/A"])
    writer.writerow(["Recommended Irrigation Date", sched_info.get("recommended_date") or "N/A"])
    writer.writerow(["Recommended Time Window", sched_info.get("recommended_time_window") or "N/A"])
    writer.writerow(["Estimated Duration", sched_info.get("duration_formatted") or "Flow rate not configured"])
    writer.writerow(["Flow Rate Status", sched_info.get("flow_rate_status", "not_configured")])
    writer.writerow(["Predictive Engine", rec.get("recommendation_engine", "AI Two-Stage Gradient Boosting ML Model")])
    writer.writerow(["Scheduling Advisory Reason", sched_info.get("reason") or rec.get("reason", "")])
    writer.writerow(["Disclaimer", L["disclaimer_text"]])
    writer.writerow([])

    # Actual Recorded Irrigation Events
    writer.writerow(["--- ACTUAL IRRIGATION EVENT LOGS ---"])
    writer.writerow([
        "Timestamp (UTC)",
        "Water Depth Applied (mm)",
        "Water Volume (Litres)",
        "Duration (Minutes)",
        "Pump Flow Rate (LPM)",
        "Source",
        "Notes"
    ])
    if data["irrigation_records"]:
        for record in data["irrigation_records"]:
            writer.writerow([
                record.timestamp.strftime("%Y-%m-%d %H:%M:%S") if record.timestamp else "",
                record.water_depth_mm,
                record.water_volume_litres,
                record.duration_minutes or "",
                record.flow_rate_lpm or "",
                record.source,
                record.notes or ""
            ])
    else:
        writer.writerow(["No actual irrigation events logged in the selected period."])
    writer.writerow([])

    # Sensor Telemetry History
    writer.writerow(["--- SENSOR READINGS & SOIL MOISTURE HISTORY ---"])
    writer.writerow([
        "Timestamp (UTC)",
        "Sensor ID",
        "Soil Moisture (%)",
        "Temperature (°C)",
        "Quality Status",
        "Quality Flags"
    ])
    if data["sensors"]:
        for s in data["sensors"]:
            m_val = s.soil_moisture if s.soil_moisture is not None else s.value
            writer.writerow([
                s.timestamp.strftime("%Y-%m-%d %H:%M:%S") if s.timestamp else "",
                s.sensor_id,
                m_val if m_val is not None else "",
                s.temperature if s.temperature is not None else "",
                s.quality_status or "valid",
                s.quality_flags or ""
            ])
    else:
        writer.writerow(["No sensor readings recorded in the selected period."])
    writer.writerow([])

    # Weather Observations History
    writer.writerow(["--- WEATHER OBSERVATIONS HISTORY ---"])
    writer.writerow([
        "Timestamp (UTC)",
        "Temperature (°C)",
        "Humidity (%)",
        "Wind Speed (m/s)",
        "Rainfall (mm)",
        "Weather Condition"
    ])
    if data["weather_records"]:
        for w in data["weather_records"]:
            writer.writerow([
                w.timestamp.strftime("%Y-%m-%d %H:%M:%S") if w.timestamp else "",
                w.temperature if w.temperature is not None else "",
                w.humidity if w.humidity is not None else "",
                w.wind_speed if w.wind_speed is not None else "",
                w.rainfall if w.rainfall is not None else "",
                w.condition or ""
            ])
    else:
        writer.writerow(["No weather observations recorded in the selected period."])

    return out.getvalue()
