import React, { useEffect, useState } from 'react';
import {
  Sparkles,
  Droplets,
  Sprout,
  AlertTriangle,
  Compass,
  Sliders,
  Info,
  CloudRain,
  Mic,
  Languages,
  Clock,
  CheckCircle2,
} from 'lucide-react';
import {
  getCropRecommendation,
  getCropModelMetrics,
  getIrrigationRecommendation,
  getFieldIrrigationRecommendation,
  getFields,
  updateField,
  getErrorMessage,
  translateDynamicRecommendation,
} from '../services/api';
import type {
  CropRecommendationResponse,
  CropModelMetrics,
  IrrigationRecommendationResponse,
  Field,
} from '../types';
import { useLanguage } from '../context/LanguageContext';
import { VoicePlayer } from '../components/common/VoicePlayer';

// Badge colours for the weather-aware scheduling decision (irrigation_schedule.action).
const SCHEDULE_BADGE: Record<string, string> = {
  IRRIGATE: 'bg-blue-100 text-blue-800',
  DEFER: 'bg-cyan-100 text-cyan-800',
  NO_IRRIGATION_NEEDED: 'bg-emerald-100 text-emerald-800',
  WITHHELD: 'bg-amber-100 text-amber-800',
};

export const RecommendationsPage: React.FC = () => {
  const { t, language, currentLanguage } = useLanguage();
  const [activeTab, setActiveTab] = useState<'crop' | 'irrigation'>('crop');

  // Crop Recommendation State
  const [cropForm, setCropForm] = useState({
    N: 90,
    P: 42,
    K: 43,
    temperature: 24.5,
    humidity: 78.0,
    ph: 6.5,
    rainfall: 180.0,
  });
  const [cropResult, setCropResult] = useState<CropRecommendationResponse | null>(null);
  const [cropMetrics, setCropMetrics] = useState<CropModelMetrics | null>(null);
  const [cropLoading, setCropLoading] = useState(false);
  const [cropError, setCropError] = useState<string | null>(null);

  // Irrigation Recommendation State
  const [fields, setFields] = useState<Field[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string>('');
  const [irrigationCustom, setIrrigationCustom] = useState({
    crop_type: 'Rice',
    growth_stage: 'flowering',
    soil_moisture: 22.0,
    temperature: 31.0,
    recent_rainfall_mm: 0.0,
    forecast_rainfall_mm: 0.0,
  });
  const [useFieldLive, setUseFieldLive] = useState(true);
  const [irrigationResult, setIrrigationResult] = useState<IrrigationRecommendationResponse | null>(null);
  const [translatedResult, setTranslatedResult] = useState<IrrigationRecommendationResponse | null>(null);
  const [irrigationLoading, setIrrigationLoading] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [irrigationError, setIrrigationError] = useState<string | null>(null);
  const [editFlowRate, setEditFlowRate] = useState<string>('');
  const [savingFlowRate, setSavingFlowRate] = useState<boolean>(false);
  const [flowRateSuccess, setFlowRateSuccess] = useState<string | null>(null);

  const handleQuickFlowRateSave = async () => {
    if (!selectedFieldId || !editFlowRate.trim()) return;
    setSavingFlowRate(true);
    setFlowRateSuccess(null);
    try {
      const rateVal = parseFloat(editFlowRate);
      await updateField(selectedFieldId, { pump_flow_rate_lpm: rateVal });
      setFields((prev) =>
        prev.map((f) => (f.field_id === selectedFieldId ? { ...f, pump_flow_rate_lpm: rateVal } : f))
      );
      setFlowRateSuccess(`Flow rate updated to ${rateVal} LPM.`);
      // Re-fetch advisory for this field to recalculate duration
      const res = await getFieldIrrigationRecommendation(selectedFieldId, language);
      setIrrigationResult(res);
      setTranslatedResult(res);
    } catch (err) {
      console.error('Failed to update flow rate:', err);
    } finally {
      setSavingFlowRate(false);
    }
  };

  useEffect(() => {
    // Load initial model metrics and available fields
    const init = async () => {
      try {
        const [metrics, flds] = await Promise.all([
          getCropModelMetrics(),
          getFields(),
        ]);
        setCropMetrics(metrics);
        setFields(flds);
        if (flds.length > 0) {
          setSelectedFieldId(flds[0].field_id);
        }
      } catch (err) {
        console.error('Failed to load initial advisory data:', err);
      }
    };
    init();
  }, []);

  // Whenever language changes or new irrigationResult arrives, dynamically translate via Sarvam AI
  useEffect(() => {
    if (!irrigationResult) {
      setTranslatedResult(null);
      return;
    }

    if (language === 'en') {
      setTranslatedResult(irrigationResult);
      return;
    }

    let isMounted = true;
    const translateCurrentAdvisory = async () => {
      try {
        setTranslating(true);
        const translated = await translateDynamicRecommendation(irrigationResult, language);
        if (isMounted) {
          setTranslatedResult(translated);
        }
      } catch (err) {
        console.warn('Sarvam dynamic translation fallback:', err);
        if (isMounted) {
          setTranslatedResult(irrigationResult);
        }
      } finally {
        if (isMounted) {
          setTranslating(false);
        }
      }
    };

    translateCurrentAdvisory();
    return () => {
      isMounted = false;
    };
  }, [language, irrigationResult]);

  // Handle Crop Recommendation Submission
  const handleCropSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCropLoading(true);
      setCropError(null);
      const res = await getCropRecommendation(cropForm);
      setCropResult(res);
    } catch (err) {
      setCropError(getErrorMessage(err));
    } finally {
      setCropLoading(false);
    }
  };

  // Quick preset selector for soil testing
  const applyPreset = (preset: 'rice' | 'maize' | 'chickpea' | 'grapes') => {
    if (preset === 'rice') {
      setCropForm({ N: 90, P: 42, K: 43, temperature: 24.0, humidity: 82.0, ph: 6.5, rainfall: 210.0 });
    } else if (preset === 'maize') {
      setCropForm({ N: 85, P: 58, K: 41, temperature: 26.0, humidity: 65.0, ph: 6.8, rainfall: 90.0 });
    } else if (preset === 'chickpea') {
      setCropForm({ N: 25, P: 68, K: 80, temperature: 18.5, humidity: 16.0, ph: 7.2, rainfall: 65.0 });
    } else if (preset === 'grapes') {
      setCropForm({ N: 22, P: 130, K: 200, temperature: 28.0, humidity: 60.0, ph: 6.2, rainfall: 70.0 });
    }
  };

  // Handle Irrigation Advisory Run
  const handleIrrigationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIrrigationLoading(true);
      setIrrigationError(null);
      let res: IrrigationRecommendationResponse;
      if (useFieldLive && selectedFieldId) {
        res = await getFieldIrrigationRecommendation(selectedFieldId, language);
      } else {
        res = await getIrrigationRecommendation(irrigationCustom, language);
      }
      setIrrigationResult(res);
      setTranslatedResult(res);
    } catch (err) {
      setIrrigationError(getErrorMessage(err));
    } finally {
      setIrrigationLoading(false);
    }
  };

  const activeAdvisory = translatedResult || irrigationResult;

  // Build audio readout string for Sarvam TTS / browser speech
  const generateAdvisorySpeechText = (rec: IrrigationRecommendationResponse): string => {
    const actionText = rec.translated_action || t(`irrigationActions.${rec.action}`, rec.action);
    const reasonText = rec.translated_reason || rec.reason;
    const waterDepth =
      rec.ml_prediction?.depth_mm !== undefined && rec.ml_prediction?.available && rec.ml_prediction.depth_mm !== null
        ? rec.ml_prediction.depth_mm
        : rec.irrigation_schedule?.recommended_irrigation_mm !== null && rec.irrigation_schedule?.recommended_irrigation_mm !== undefined
        ? rec.irrigation_schedule.recommended_irrigation_mm
        : rec.recommended_water_mm;
    const validDepth = (waterDepth !== null && waterDepth !== undefined) ? Number(waterDepth) : 0;
    const waterPart = validDepth > 0 ? `${validDepth} mm water.` : '';
    return `${actionText}. ${waterPart} ${reasonText}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t('recommendations.title', 'Agricultural Intelligence & Irrigation Advisory')}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {t('recommendations.subtitle', 'Machine learning crop suitability classification and AI-powered predictive ML irrigation water management.')}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {/* Farmer Voice & Chat Assistant Button */}
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-agripulse-assistant'))}
            className="inline-flex items-center space-x-2 px-3 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
            title="Ask question by voice or chat in your language"
          >
            <Mic className="w-3.5 h-3.5 text-emerald-200" />
            <span>{t('dashboard.askVoiceAssistant', 'AI Voice & Chat Assistant')}</span>
          </button>

          {/* Tab switcher */}
          <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => setActiveTab('crop')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'crop'
                  ? 'bg-white text-emerald-800 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {t('recommendations.cropTab', 'Crop Suitability')}
            </button>
            <button
              onClick={() => setActiveTab('irrigation')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === 'irrigation'
                  ? 'bg-white text-emerald-800 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {t('recommendations.irrigationTab', 'AI Irrigation Recommendation')}
            </button>
          </div>
        </div>
      </div>

      {/* ────────────────── TAB 1: CROP RECOMMENDATION ────────────────── */}
      {activeTab === 'crop' && (
        <div className="space-y-6">
          {/* Presets and Guidance */}
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center space-x-2 text-slate-600">
              <Compass className="w-4 h-4 text-emerald-600" />
              <span className="font-semibold text-slate-800">Quick Soil &amp; Climate Presets:</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => applyPreset('rice')}
                className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-medium cursor-pointer"
              >
                Paddy / Rice Conditions
              </button>
              <button
                type="button"
                onClick={() => applyPreset('maize')}
                className="px-2.5 py-1 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 font-medium cursor-pointer"
              >
                Maize / Cereal Loam
              </button>
              <button
                type="button"
                onClick={() => applyPreset('chickpea')}
                className="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-medium cursor-pointer"
              >
                Semi-Arid Legumes (Chickpea)
              </button>
              <button
                type="button"
                onClick={() => applyPreset('grapes')}
                className="px-2.5 py-1 rounded-lg bg-purple-50 text-purple-700 hover:bg-purple-100 font-medium cursor-pointer"
              >
                High-Potassium Orchards (Grapes)
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Input Form */}
            <div className="lg:col-span-1 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
              <div className="flex items-center space-x-2 pb-3 border-b border-slate-100">
                <Sliders className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-slate-900 text-sm">Soil &amp; Climate Parameters</h3>
              </div>

              {cropError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                  {cropError}
                </div>
              )}

              <form onSubmit={handleCropSubmit} className="space-y-3.5">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.nitrogen', 'Nitrogen (N)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      max="150"
                      value={cropForm.N}
                      onChange={(e) => setCropForm({ ...cropForm, N: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                    <span className="text-[10px] text-slate-400">kg/ha</span>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.phosphorus', 'Phosphorus (P)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      max="150"
                      value={cropForm.P}
                      onChange={(e) => setCropForm({ ...cropForm, P: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                    <span className="text-[10px] text-slate-400">kg/ha</span>
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.potassium', 'Potassium (K)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      max="210"
                      value={cropForm.K}
                      onChange={(e) => setCropForm({ ...cropForm, K: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                    <span className="text-[10px] text-slate-400">kg/ha</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.ambientTemp', 'Temp (°C)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={cropForm.temperature}
                      onChange={(e) => setCropForm({ ...cropForm, temperature: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.humidity', 'Humidity (%)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      max="100"
                      value={cropForm.humidity}
                      onChange={(e) => setCropForm({ ...cropForm, humidity: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.ph', 'Soil pH (0-14)')}
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="14"
                      value={cropForm.ph}
                      onChange={(e) => setCropForm({ ...cropForm, ph: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                      {t('recommendations.rainfall', 'Rainfall (mm)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={cropForm.rainfall}
                      onChange={(e) => setCropForm({ ...cropForm, rainfall: parseFloat(e.target.value) || 0 })}
                      className="w-full px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={cropLoading}
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-xs transition-colors flex items-center justify-center space-x-1.5 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{cropLoading ? t('recommendations.generating', 'Evaluating Agronomic Suitability...') : t('recommendations.generate', 'Predict Suitable Crops')}</span>
                </button>
              </form>
            </div>

            {/* Results Display */}
            <div className="lg:col-span-2 space-y-6">
              {cropResult ? (
                <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2">
                    <div>
                      <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                        {t('recommendations.action', 'Primary Crop Recommendation')}
                      </span>
                      <div className="flex items-center space-x-3 mt-1">
                        <span className="text-2xl font-black text-emerald-700 capitalize tracking-tight">
                          {cropResult.recommended_crop}
                        </span>
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                          {Math.round(cropResult.confidence * 100)}% {t('recommendations.confidence', 'Confidence')}
                        </span>
                      </div>
                    </div>
                    {/* Audio Readout for Crop Recommendation */}
                    <VoicePlayer
                      text={`Recommended crop is ${cropResult.recommended_crop} with ${Math.round(cropResult.confidence * 100)}% confidence. ${cropResult.agronomic_explanation}`}
                      label="Listen to Recommendation"
                    />
                  </div>

                  {/* Top Candidates Probability Breakdown */}
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2.5">
                      {t('recommendations.topCandidates', 'Top Recommended Crops by Probability')}
                    </h4>
                    <div className="space-y-2">
                      {cropResult.top_candidates.map((cand) => (
                        <div key={cand.crop} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="font-semibold text-slate-700 capitalize">{cand.crop}</span>
                            <span className="text-slate-500 font-mono">{cand.confidence_pct}%</span>
                          </div>
                          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                            <div
                              className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                              style={{ width: `${Math.min(100, cand.confidence_pct)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Agronomic Explanation */}
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-xs leading-relaxed space-y-1">
                    <div className="font-semibold text-slate-900 flex items-center space-x-1.5">
                      <Info className="w-4 h-4 text-emerald-600" />
                      <span>{t('recommendations.reasoning', 'Agronomic Analysis & Explanation:')}</span>
                    </div>
                    <p>{cropResult.agronomic_explanation}</p>
                  </div>
                </div>
              ) : (
                <div className="bg-white p-10 rounded-2xl border border-slate-200/80 shadow-xs text-center flex flex-col items-center justify-center space-y-2 text-slate-400">
                  <Sprout className="w-10 h-10 text-emerald-200" />
                  <p className="text-sm font-medium text-slate-600">No crop recommendation generated yet.</p>
                  <p className="text-xs max-w-sm">
                    Enter soil nutrients (NPK), climate metrics, and rainfall to classify optimal crops.
                  </p>
                </div>
              )}

              {/* Model Verification & Metrics card */}
              {cropMetrics && (
                <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-4 h-4 text-emerald-600" />
                      <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                        Trained Machine Learning Model
                      </h4>
                    </div>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                      {cropMetrics.algorithm}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Test Accuracy</div>
                      <div className="font-bold text-slate-800">
                        {Math.round(cropMetrics.test_accuracy * 1000) / 10}%
                      </div>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Macro F1 Score</div>
                      <div className="font-bold text-slate-800">
                        {Math.round(cropMetrics.macro_f1 * 1000) / 10}%
                      </div>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Training Samples</div>
                      <div className="font-bold text-slate-800">{cropMetrics.train_samples}</div>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Holdout Tests</div>
                      <div className="font-bold text-slate-800">{cropMetrics.test_samples}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ────────────────── TAB 2: IRRIGATION ADVISORY ────────────────── */}
      {activeTab === 'irrigation' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Form Side */}
          <div className="lg:col-span-1 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <Droplets className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-slate-900 text-sm">
                  {t('recommendations.irrigationTab', 'Irrigation Evaluation')}
                </h3>
              </div>
            </div>

            {irrigationError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                {irrigationError}
              </div>
            )}

            {/* Live Field vs Manual Toggle */}
            <div className="grid grid-cols-2 gap-1 p-1 bg-slate-100 rounded-xl text-xs font-semibold">
              <button
                type="button"
                onClick={() => setUseFieldLive(true)}
                className={`py-1.5 rounded-lg transition-all cursor-pointer ${
                  useFieldLive ? 'bg-white text-blue-700 shadow-2xs' : 'text-slate-600'
                }`}
              >
                {t('recommendations.liveFieldData', 'Live Field Telemetry')}
              </button>
              <button
                type="button"
                onClick={() => setUseFieldLive(false)}
                className={`py-1.5 rounded-lg transition-all cursor-pointer ${
                  !useFieldLive ? 'bg-white text-blue-700 shadow-2xs' : 'text-slate-600'
                }`}
              >
                {t('recommendations.customParameters', 'Manual Parameters')}
              </button>
            </div>

            <form onSubmit={handleIrrigationSubmit} className="space-y-4">
              {useFieldLive ? (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {t('recommendations.selectField', 'Select Field')}
                  </label>
                  <select
                    value={selectedFieldId}
                    onChange={(e) => setSelectedFieldId(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 cursor-pointer"
                    required
                  >
                    {fields.map((f) => (
                      <option key={f.field_id} value={f.field_id}>
                        {f.name} ({f.field_id}) — {f.crop_type}
                      </option>
                    ))}
                    {fields.length === 0 && <option value="">No registered fields found</option>}
                  </select>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Pulls latest TimescaleDB sensor telemetry and OpenWeather observations automatically.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      {t('recommendations.cropType', 'Crop Type')}
                    </label>
                    <input
                      type="text"
                      value={irrigationCustom.crop_type}
                      onChange={(e) => setIrrigationCustom({ ...irrigationCustom, crop_type: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      {t('recommendations.growthStage', 'Growth Stage')}
                    </label>
                    <select
                      value={irrigationCustom.growth_stage}
                      onChange={(e) => setIrrigationCustom({ ...irrigationCustom, growth_stage: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 cursor-pointer"
                    >
                      <option value="seedling">Seedling (Moderate watering)</option>
                      <option value="vegetative">Vegetative (Active growth)</option>
                      <option value="flowering">Flowering (Critical reproductive peak)</option>
                      <option value="maturity">Maturity (Pre-harvest drying)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      {t('recommendations.soilMoisture', 'Soil Moisture (%)')}
                    </label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      max="100"
                      value={irrigationCustom.soil_moisture}
                      onChange={(e) => setIrrigationCustom({ ...irrigationCustom, soil_moisture: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        {t('recommendations.rainfall', 'Recent Rain (mm)')}
                      </label>
                      <input
                        type="number"
                        step="any"
                        min="0"
                        value={irrigationCustom.recent_rainfall_mm}
                        onChange={(e) => setIrrigationCustom({ ...irrigationCustom, recent_rainfall_mm: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        {t('recommendations.ambientTemp', 'Temp (°C)')}
                      </label>
                      <input
                        type="number"
                        step="any"
                        value={irrigationCustom.temperature}
                        onChange={(e) => setIrrigationCustom({ ...irrigationCustom, temperature: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                      />
                    </div>
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={irrigationLoading || (useFieldLive && !selectedFieldId)}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-xl shadow-xs transition-colors flex items-center justify-center space-x-1.5 cursor-pointer"
              >
                <Droplets className="w-4 h-4" />
                <span>
                  {irrigationLoading ? t('recommendations.generating', 'Computing Deficit...') : t('recommendations.generate', 'Calculate Irrigation Requirement')}
                </span>
              </button>
            </form>
          </div>

          {/* Results Side */}
          <div className="lg:col-span-2 space-y-6">
            {activeAdvisory ? (
              <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-5">
                {/* Indic Translation Status Banner */}
                {language !== 'en' && (
                  <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs">
                    <div className="flex items-center space-x-2">
                      <Languages className="w-4 h-4 text-emerald-600" />
                      <span className="font-semibold">
                        {t('recommendations.dynamicTranslationActive', 'Translated via Sarvam AI Indic Engine')} ({currentLanguage.nativeName})
                      </span>
                    </div>
                    {translating && (
                      <span className="text-[11px] font-medium text-emerald-700 animate-pulse">
                        Updating translation...
                      </span>
                    )}
                  </div>
                )}

                {/* Alerts (rule-based). EMERGENCY is shown first and in red. */}
                {activeAdvisory.alerts && activeAdvisory.alerts.alerts.length > 0 && (
                  <div className="space-y-2" role="alert">
                    {activeAdvisory.alerts.alerts.map((a: any) => {
                      const alertTitle = a.translated_title || a.title;
                      const alertMessage = a.translated_message || a.message;
                      const alertAction = a.translated_recommended_action || a.recommended_action;
                      const alertSpeech = `${alertTitle}. ${alertMessage}. ${alertAction}`;

                      return (
                        <div
                          key={a.code}
                          className={`p-3.5 rounded-xl border text-xs leading-relaxed flex items-start justify-between gap-3 ${
                            a.level === 'EMERGENCY'
                              ? 'bg-rose-50 border-rose-300 text-rose-900'
                              : a.level === 'WARNING'
                              ? 'bg-amber-50 border-amber-200 text-amber-900'
                              : 'bg-slate-50 border-slate-200 text-slate-700'
                          }`}
                        >
                          <div className="space-y-1">
                            <div className="font-bold flex items-center space-x-1.5">
                              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
                              <span>
                                {a.level === 'EMERGENCY' ? 'EMERGENCY / అత్యవసరం / आपातकाल: ' : ''}
                                {alertTitle}
                              </span>
                            </div>
                            <p>{alertMessage}</p>
                            <p className="font-semibold">{alertAction}</p>
                          </div>
                          {/* Audio Player for this alert in selected language */}
                          <VoicePlayer
                            text={alertSpeech}
                            languageCode={language}
                            compact
                            title="Listen to this alert in your language"
                          />
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Top Action & Water Volume Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
                  <div>
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                      {t('recommendations.action', 'Agronomic Action')}
                    </span>
                    <div className="flex items-center space-x-2 mt-1">
                      <span
                        className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-extrabold tracking-wide ${
                          activeAdvisory.action === 'IRRIGATE_IMMEDIATELY'
                            ? 'bg-rose-100 text-rose-800'
                            : activeAdvisory.action === 'IRRIGATE_LIGHT'
                            ? 'bg-blue-100 text-blue-800'
                            : activeAdvisory.action === 'DEFER_DUE_TO_RAIN'
                            ? 'bg-cyan-100 text-cyan-800'
                            : 'bg-emerald-100 text-emerald-800'
                        }`}
                      >
                        {activeAdvisory.translated_action || t(`irrigationActions.${activeAdvisory.action}`, activeAdvisory.action.replace(/_/g, ' '))}
                      </span>
                      <span className="text-xs font-semibold text-slate-500">
                        {t('recommendations.urgency', 'Urgency')}: {activeAdvisory.translated_urgency || t(`irrigationActions.${activeAdvisory.urgency}`, activeAdvisory.urgency)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <span className="text-[11px] font-medium text-slate-400 block">
                        {t('recommendations.waterAmount', 'Recommended Water')}
                      </span>
                      <div className="flex items-baseline justify-end space-x-1.5">
                        <span className="text-2xl font-black text-slate-900">
                          {activeAdvisory.ml_prediction?.depth_mm !== undefined && activeAdvisory.ml_prediction?.available
                            ? `${activeAdvisory.ml_prediction.depth_mm} mm`
                            : activeAdvisory.irrigation_schedule?.recommended_irrigation_mm !== null && activeAdvisory.irrigation_schedule?.recommended_irrigation_mm !== undefined
                            ? `${activeAdvisory.irrigation_schedule.recommended_irrigation_mm} mm`
                            : `${activeAdvisory.recommended_water_mm} mm`}
                        </span>
                        {activeAdvisory.ml_prediction?.available ? (
                          <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                            ML Model
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                            Agronomic Baseline
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Voice Readout Button for the Entire Advisory */}
                    <VoicePlayer
                      text={generateAdvisorySpeechText(activeAdvisory)}
                      languageCode={language}
                      label={t('recommendations.listenAdvice', 'Listen to Advice')}
                    />
                  </div>
                </div>

                {/* Model Engine Provenance Pill */}
                <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold text-slate-700">{t('scheduling.predictiveEngine', 'Predictive Engine')}:</span>
                    <span className="font-bold text-slate-800">
                      {activeAdvisory.ml_prediction?.model_name || activeAdvisory.recommendation_engine}
                    </span>
                  </div>
                  {activeAdvisory.factors_evaluated?.fao56_deficit_mm !== undefined && (
                    <div className="text-[11px] text-slate-500 font-medium">
                      {t('scheduling.faoBenchmark', 'Agronomic FAO-56 Benchmark')}: <span className="font-bold text-slate-700">{activeAdvisory.factors_evaluated.fao56_deficit_mm} mm</span>
                    </div>
                  )}
                </div>

                {/* PART 1: IRRIGATION SCHEDULING RECOMMENDATION */}
                {activeAdvisory.scheduling_recommendation && (
                  <div className="p-5 rounded-2xl border-2 border-emerald-500/40 bg-gradient-to-br from-emerald-50/80 via-teal-50/30 to-white shadow-xs space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-emerald-100 gap-2">
                      <div className="flex items-center space-x-2.5">
                        <div className="p-2 bg-emerald-600 text-white rounded-xl shadow-xs">
                          <Clock className="w-5 h-5" />
                        </div>
                        <div>
                          <h3 className="text-xs font-black text-emerald-950 uppercase tracking-wider">
                            {t('scheduling.title', 'IRRIGATION SCHEDULING RECOMMENDATION')}
                          </h3>
                          <p className="text-[11px] text-emerald-700">
                            {t('scheduling.subtitle', 'Advisory schedule & estimated duration derived from ML requirement and pump flow rate')}
                          </p>
                        </div>
                      </div>
                      <span className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 self-start sm:self-auto">
                        {t('scheduling.farmerAdvisory', 'Farmer Advisory')}
                      </span>
                    </div>

                    {/* Primary 3 Scheduling Metric Tiles */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                      {/* 1. ML-Predicted Water Requirement */}
                      <div className="p-3.5 bg-white rounded-xl border border-emerald-100/90 shadow-2xs">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">
                          {t('scheduling.mlRequirement', 'ML Water Requirement')}
                        </span>
                        <div className="text-xl font-black text-slate-900 mt-1">
                          {activeAdvisory.scheduling_recommendation.predicted_water_depth_mm !== null
                            ? `${activeAdvisory.scheduling_recommendation.predicted_water_depth_mm} mm`
                            : `${activeAdvisory.recommended_water_mm} mm`}
                        </div>
                        <div className="text-[11px] font-semibold text-emerald-700 mt-0.5">
                          {activeAdvisory.scheduling_recommendation.water_volume_litres !== null
                            ? `${activeAdvisory.scheduling_recommendation.water_volume_litres.toLocaleString()} Litres`
                            : 'Volume N/A'}
                        </div>
                      </div>

                      {/* 2. Recommended Date & Window */}
                      <div className="p-3.5 bg-white rounded-xl border border-emerald-100/90 shadow-2xs">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">
                          {t('scheduling.recommendedDateWindow', 'Recommended Date & Window')}
                        </span>
                        <div className="text-sm font-bold text-slate-900 mt-1">
                          {activeAdvisory.scheduling_recommendation.recommended_irrigation_date || t('scheduling.today', 'Today')}
                        </div>
                        <div className="text-xs font-extrabold text-blue-700 mt-0.5">
                          {activeAdvisory.scheduling_recommendation.recommended_time_window || t('scheduling.immediate', 'Immediate')}
                        </div>
                      </div>

                      {/* 3. Estimated Duration & Flow Rate */}
                      <div className="p-3.5 bg-white rounded-xl border border-emerald-100/90 shadow-2xs">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">
                          {t('scheduling.estimatedDuration', 'Estimated Duration')}
                        </span>
                        <div className="text-lg font-black text-slate-900 mt-1">
                          {activeAdvisory.scheduling_recommendation.estimated_duration_formatted}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5 flex items-center justify-between">
                          <span>{t('scheduling.flowRate', 'Flow Rate')}:</span>
                          <span className="font-bold text-slate-700">
                            {activeAdvisory.scheduling_recommendation.pump_flow_rate_lpm
                              ? `${activeAdvisory.scheduling_recommendation.pump_flow_rate_lpm} LPM`
                              : t('scheduling.flowRateNotConfigured', 'Flow rate not configured')}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Crop & Field Details */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-xl bg-emerald-100/40 text-[11px]">
                      <div>
                        <span className="text-emerald-800 font-medium block">{t('scheduling.cropType', 'Crop Type')}:</span>
                        <span className="font-bold text-slate-900 capitalize">
                          {fields.find((f) => f.field_id === selectedFieldId)?.crop_type || irrigationCustom.crop_type}
                        </span>
                      </div>
                      <div>
                        <span className="text-emerald-800 font-medium block">{t('scheduling.growthStage', 'Growth Stage')}:</span>
                        <span className="font-bold text-slate-900 capitalize">
                          {irrigationCustom.growth_stage || 'Active'}
                        </span>
                      </div>
                      <div>
                        <span className="text-emerald-800 font-medium block">{t('scheduling.fieldArea', 'Field Area')}:</span>
                        <span className="font-bold text-slate-900">
                          {activeAdvisory.scheduling_recommendation.field_area_hectares
                            ? `${activeAdvisory.scheduling_recommendation.field_area_hectares} ha`
                            : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-emerald-800 font-medium block">{t('scheduling.irrigationMethod', 'Irrigation Method')}:</span>
                        <span className="font-bold text-slate-900">
                          {fields.find((f) => f.field_id === selectedFieldId)?.irrigation_method || 'Drip'}
                        </span>
                      </div>
                    </div>

                    {/* Reason for Recommended Time & Window */}
                    <div className="p-3.5 rounded-xl bg-white/95 border border-emerald-200 text-xs text-slate-800 space-y-1.5 shadow-2xs">
                      <div className="font-bold text-emerald-950 flex items-center space-x-1.5">
                        <Info className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>{t('scheduling.reasonTiming', 'Reason for Recommended Timing')}:</span>
                      </div>
                      <p className="leading-relaxed text-slate-700">
                        {activeAdvisory.scheduling_recommendation.reason}
                      </p>
                      <div className="text-[10px] text-slate-500 italic pt-1 border-t border-slate-100">
                        {activeAdvisory.scheduling_recommendation.disclaimer}
                      </div>
                    </div>

                    {/* Quick Pump Flow Rate Configuration Inline */}
                    {useFieldLive && selectedFieldId && (
                      <div className="pt-2 border-t border-emerald-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                        <div className="text-[11px] text-slate-600">
                          <b>Pump Flow Rate (LPM):</b> Set or adjust actual pump capacity to calculate exact watering durations.
                        </div>
                        <div className="flex items-center space-x-2">
                          <input
                            type="number"
                            step="any"
                            min="1"
                            placeholder="LPM (e.g. 250)"
                            value={editFlowRate}
                            onChange={(e) => setEditFlowRate(e.target.value)}
                            className="w-28 px-2.5 py-1 text-xs rounded-lg border border-slate-300 focus:outline-emerald-600 font-semibold"
                          />
                          <button
                            type="button"
                            onClick={handleQuickFlowRateSave}
                            disabled={savingFlowRate || !editFlowRate}
                            className="px-3 py-1 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                          >
                            {savingFlowRate ? 'Saving...' : 'Set Flow Rate'}
                          </button>
                        </div>
                      </div>
                    )}
                    {flowRateSuccess && (
                      <div className="text-[11px] text-emerald-800 font-medium">
                        ✓ {flowRateSuccess}
                      </div>
                    )}
                  </div>
                )}

                {/* Weather-aware scheduling decision */}
                {activeAdvisory.irrigation_schedule ? (
                  <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/50 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold text-slate-900 text-xs flex items-center space-x-1.5">
                          <CloudRain className="w-4 h-4 text-blue-600" />
                          <span>{t('recommendations.schedulePlan', 'Weather-Aware Scheduling Decision')}</span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          Considers local rainfall forecasts to prevent over-irrigation.
                        </p>
                      </div>
                      <span
                        className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-extrabold tracking-wide ${
                          SCHEDULE_BADGE[activeAdvisory.irrigation_schedule.action] ?? 'bg-slate-100 text-slate-800'
                        }`}
                      >
                        {t(`irrigationActions.${activeAdvisory.irrigation_schedule.action}`, activeAdvisory.irrigation_schedule.action.replace(/_/g, ' '))}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2.5 bg-white rounded-xl border border-slate-100">
                        <div className="text-slate-400 text-[10px]">Scheduled Water Depth</div>
                        <div className="font-bold text-slate-800">
                          {activeAdvisory.irrigation_schedule.recommended_irrigation_mm !== null
                            ? `${activeAdvisory.irrigation_schedule.recommended_irrigation_mm} mm`
                            : 'No recommendation'}
                        </div>
                      </div>
                      <div className="p-2.5 bg-white rounded-xl border border-slate-100">
                        <div className="text-slate-400 text-[10px]">Water Volume</div>
                        {activeAdvisory.irrigation_schedule.volume ? (
                          <>
                            <div className="font-bold text-slate-800">
                              {activeAdvisory.irrigation_schedule.volume.litres.toLocaleString()} L
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {activeAdvisory.irrigation_schedule.volume.cubic_metres} m³
                            </div>
                          </>
                        ) : (
                          <div className="font-bold text-slate-800">
                            {activeAdvisory.irrigation_schedule.action === 'IRRIGATE'
                              ? 'Not calculated'
                              : 'Not applicable'}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Schedule Reasons (translated or raw) */}
                    {(activeAdvisory.irrigation_schedule.translated_reasons || activeAdvisory.irrigation_schedule.reasons).length > 0 && (
                      <ul className="list-disc pl-4 text-xs text-slate-700 leading-relaxed space-y-0.5">
                        {(activeAdvisory.irrigation_schedule.translated_reasons || activeAdvisory.irrigation_schedule.reasons).map((r: string, i: number) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    )}

                    {activeAdvisory.irrigation_schedule.reevaluate_after_hours !== null && (
                      <p className="text-[11px] text-slate-600">
                        Re-evaluate in about {activeAdvisory.irrigation_schedule.reevaluate_after_hours} h.
                      </p>
                    )}
                  </div>
                ) : (
                  (activeAdvisory.translated_scheduling_note || activeAdvisory.scheduling_note) && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-600">
                      <span className="font-semibold text-slate-700">No weather-aware schedule: </span>
                      {activeAdvisory.translated_scheduling_note || activeAdvisory.scheduling_note}
                    </div>
                  )
                )}

                {/* Plain Text Rationale */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-xs leading-relaxed space-y-1">
                  <div className="font-semibold text-slate-900 flex items-center space-x-1.5">
                    <Info className="w-4 h-4 text-blue-600" />
                    <span>{t('recommendations.reasoning', 'Explainability & Rationale:')}</span>
                  </div>
                  <p>{activeAdvisory.translated_reason || activeAdvisory.reason}</p>
                </div>

                {/* Factors Evaluated Table */}
                <div>
                  <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                    Evaluated Telemetry Factors
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">
                        {t('recommendations.soilMoisture', 'Current Moisture')}
                      </div>
                      <div className="font-bold text-slate-800">
                        {activeAdvisory.factors_evaluated.current_soil_moisture_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Critical Threshold</div>
                      <div className="font-bold text-slate-800">
                        {activeAdvisory.factors_evaluated.critical_threshold_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Optimal Target</div>
                      <div className="font-bold text-slate-800">
                        {activeAdvisory.factors_evaluated.optimal_target_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-xl">
                      <div className="text-slate-400 text-[10px]">Sensor Freshness</div>
                      <div className="font-bold text-slate-800 capitalize">
                        {activeAdvisory.sensor_freshness}
                      </div>
                    </div>
                    {activeAdvisory.factors_evaluated.fao56_deficit_mm !== undefined && (
                      <div className="p-2.5 bg-slate-50 rounded-xl">
                        <div className="text-slate-400 text-[10px]">FAO-56 Deficit Benchmark</div>
                        <div className="font-bold text-slate-800">
                          {activeAdvisory.factors_evaluated.fao56_deficit_mm} mm
                        </div>
                      </div>
                    )}
                    {activeAdvisory.ml_prediction?.probability != null && (
                      <div className="p-2.5 bg-slate-50 rounded-xl">
                        <div className="text-slate-400 text-[10px]">ML Probability</div>
                        <div className="font-bold text-emerald-700">
                          {(activeAdvisory.ml_prediction.probability * 100).toFixed(1)}%
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Disclaimer */}
                <div className="p-3 rounded-xl bg-amber-50/70 border border-amber-200 text-[11px] text-amber-900 space-y-0.5">
                  <div className="font-semibold">Safety &amp; Actuation Boundary:</div>
                  <p>{activeAdvisory.translated_limitations || activeAdvisory.limitations}</p>
                </div>
              </div>
            ) : (
              <div className="bg-white p-10 rounded-2xl border border-slate-200/80 shadow-xs text-center flex flex-col items-center justify-center space-y-2 text-slate-400">
                <Droplets className="w-10 h-10 text-blue-200" />
                <p className="text-sm font-medium text-slate-600">
                  {t('recommendations.noAdvisoryTitle', 'No irrigation recommendation evaluated yet.')}
                </p>
                <p className="text-xs max-w-sm">
                  {t('recommendations.emptyAdvisoryPrompt', 'Select a monitored field or enter custom moisture metrics to calculate water requirement using the AI ML predictive model.')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default RecommendationsPage;
