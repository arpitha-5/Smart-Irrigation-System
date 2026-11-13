import axios, { AxiosError } from 'axios';
import type {
  Farmer,
  FarmerCreate,
  FarmerUpdate,
  Field,
  FieldCreate,
  FieldUpdate,
  Crop,
  CropCreate,
  CropPatch,
  Sensor,
  SensorCreate,
  SensorUpdate,
  SensorReading,
  SensorReadingIn,
  WeatherData,
  WeatherFetchResponse,
  SearchedWeather,
  PlaceResult,
  DataQualityStats,
  DataQualityEvent,
  SystemStatus,
  DashboardSummary,
  IrrigationLog,
  IrrigationLogCreate,
  ReportSummary,
  FarmerLoginPayload,
  FarmerRegisterPayload,
  AuthResponse,
  Alert,
  ReportsSummary,
  DailyReportItem,
  NotificationTestPayload,
  IrrigationSchedule,
  IrrigationScheduleCreate,
  IrrigationScheduleUpdate,
  FarmerDashboard,
  FarmAlert,
  DigitalTwinResponse,
  CropStressResponse,
  WaterBudgetResponse,
  WaterAnalytics,
} from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010';
export const API_DOCS_URL = `${API_BASE_URL}/docs`;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 45000,
});

// Automatically inject JWT Bearer token into outgoing requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('agripulse_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data?.error?.message) {
      return data.error.message;
    }
    if (data?.detail) {
      if (Array.isArray(data.detail)) {
        return data.detail.map((d: any) => `${d.loc?.join('.') || 'field'}: ${d.msg}`).join(', ');
      }
      return String(data.detail);
    }
    if (error.message) {
      return error.message;
    }
  }
  return 'An unexpected error occurred';
}

// ── System & Dashboard ──────────────────────────────────────────────────────────
export async function getHealth(): Promise<{ status: string }> {
  const { data } = await apiClient.get('/health');
  return data;
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const { data } = await apiClient.get<SystemStatus>('/system/status');
  return data;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>('/dashboard/summary');
  return data;
}

export async function seedDemoData(): Promise<any> {
  const { data } = await apiClient.post('/demo/seed');
  return data;
}

// ── Authentication & Farmer Onboarding ────────────────────────────────────────
export async function loginFarmer(payload: FarmerLoginPayload): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>('/auth/login', payload);
  return data;
}

export async function registerFarmer(payload: FarmerRegisterPayload): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>('/auth/register', payload);
  return data;
}

export async function getCurrentUser(): Promise<{ farmer: Farmer; fields: Field[] }> {
  const { data } = await apiClient.get<{ farmer: Farmer; fields: Field[] }>('/auth/me');
  return data;
}

export async function getFarmerProfile(): Promise<Farmer & { fields: Field[] }> {
  const { data } = await apiClient.get<Farmer & { fields: Field[] }>('/farmers/profile');
  return data;
}

export async function updateFarmerProfile(payload: FarmerUpdate): Promise<Farmer> {
  const { data } = await apiClient.put<Farmer>('/farmers/profile', payload);
  return data;
}

// ── Farmers ───────────────────────────────────────────────────────────────────
export async function getFarmers(): Promise<Farmer[]> {
  const { data } = await apiClient.get<Farmer[]>('/farmers');
  return data;
}

export async function getFarmer(farmerId: string): Promise<Farmer & { fields: Field[] }> {
  const { data } = await apiClient.get(`/farmers/${farmerId}`);
  return data;
}

export async function createFarmer(payload: FarmerCreate): Promise<Farmer> {
  const { data } = await apiClient.post<Farmer>('/farmers', payload);
  return data;
}

export async function updateFarmer(farmerId: string, payload: FarmerUpdate): Promise<Farmer> {
  const { data } = await apiClient.put<Farmer>(`/farmers/${farmerId}`, payload);
  return data;
}

export async function deleteFarmer(farmerId: string): Promise<void> {
  await apiClient.delete(`/farmers/${farmerId}`);
}

// ── Fields ────────────────────────────────────────────────────────────────────
export async function getFields(farmerId?: string): Promise<Field[]> {
  const { data } = await apiClient.get<Field[]>('/fields', {
    params: farmerId ? { farmer_id: farmerId } : {},
  });
  return data;
}

export async function getField(fieldId: string): Promise<Field & { farmer?: Farmer; sensors?: Sensor[]; crops?: Crop[] }> {
  const { data } = await apiClient.get(`/fields/${fieldId}`);
  return data;
}

export async function createField(payload: FieldCreate): Promise<Field> {
  const { data } = await apiClient.post<Field>('/fields', payload);
  return data;
}

export async function updateField(fieldId: string, payload: FieldUpdate): Promise<Field> {
  const { data } = await apiClient.put<Field>(`/fields/${fieldId}`, payload);
  return data;
}

export async function deleteField(fieldId: string): Promise<void> {
  await apiClient.delete(`/fields/${fieldId}`);
}

export async function getFieldSensors(fieldId: string): Promise<Sensor[]> {
  const { data } = await apiClient.get<Sensor[]>(`/fields/${fieldId}/sensors`);
  return data;
}

// ── Crops ─────────────────────────────────────────────────────────────────────
export async function getCrops(fieldId?: string): Promise<Crop[]> {
  const { data } = await apiClient.get<Crop[]>('/crops', {
    params: fieldId ? { field_id: fieldId } : {},
  });
  return data;
}

export async function getCrop(cropId: string): Promise<Crop> {
  const { data } = await apiClient.get<Crop>(`/crops/${cropId}`);
  return data;
}

export async function createCrop(payload: CropCreate): Promise<Crop> {
  const { data } = await apiClient.post<Crop>('/crops', payload);
  return data;
}

export async function updateCrop(cropId: string, payload: CropPatch): Promise<Crop> {
  const { data } = await apiClient.put<Crop>(`/crops/${cropId}`, payload);
  return data;
}

export async function deleteCrop(cropId: string): Promise<void> {
  await apiClient.delete(`/crops/${cropId}`);
}

// ── Sensors ───────────────────────────────────────────────────────────────────
export async function getSensors(fieldId?: string): Promise<Sensor[]> {
  const { data } = await apiClient.get<Sensor[]>('/sensors', {
    params: fieldId ? { field_id: fieldId } : {},
  });
  return data;
}

export async function getSensor(sensorId: string): Promise<Sensor> {
  const { data } = await apiClient.get<Sensor>(`/sensors/${sensorId}`);
  return data;
}

export async function createSensor(payload: SensorCreate): Promise<Sensor> {
  const { data } = await apiClient.post<Sensor>('/sensors', payload);
  return data;
}

export async function updateSensor(sensorId: string, payload: SensorUpdate): Promise<Sensor> {
  const { data } = await apiClient.put<Sensor>(`/sensors/${sensorId}`, payload);
  return data;
}

export async function deleteSensor(sensorId: string): Promise<void> {
  await apiClient.delete(`/sensors/${sensorId}`);
}

export async function setSensorStatus(sensorId: string, status: 'active' | 'inactive'): Promise<Sensor> {
  const { data } = await apiClient.put<Sensor>(`/sensors/${sensorId}/status`, { status });
  return data;
}

// ── Sensor Readings ────────────────────────────────────────────────────────────
export async function getSensorReadings(params?: {
  sensor_id?: string;
  field_id?: string;
  measurement_type?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}): Promise<SensorReading[]> {
  const { data } = await apiClient.get<SensorReading[]>('/sensor/readings', { params });
  return data;
}

export async function ingestReading(payload: SensorReadingIn): Promise<any> {
  const { data } = await apiClient.post('/sensor/readings', payload);
  return data;
}

export function getExportReadingsUrl(params?: { sensor_id?: string; field_id?: string }): string {
  const searchParams = new URLSearchParams();
  if (params?.sensor_id) searchParams.append('sensor_id', params.sensor_id);
  if (params?.field_id) searchParams.append('field_id', params.field_id);
  const q = searchParams.toString();
  return `${API_BASE_URL}/sensor/readings/export.csv${q ? '?' + q : ''}`;
}

// ── Weather ───────────────────────────────────────────────────────────────────
export async function fetchLiveWeather(fieldId: string): Promise<WeatherFetchResponse> {
  const { data } = await apiClient.get<WeatherFetchResponse>(`/weather/${fieldId}`);
  return data;
}

export async function getWeatherHistory(fieldId: string, limit = 50): Promise<WeatherData[]> {
  const { data } = await apiClient.get<WeatherData[]>(`/weather/${fieldId}/history`, {
    params: { limit },
  });
  return data;
}

export async function getAllWeatherObservations(limit = 100): Promise<WeatherData[]> {
  const { data } = await apiClient.get<WeatherData[]>('/weather/observations', {
    params: { limit },
  });
  return data;
}

export async function getLatestStoredWeather(fieldId: string): Promise<WeatherData> {
  const { data } = await apiClient.get<WeatherData>(`/weather/${fieldId}/latest`);
  return data;
}

export async function searchLocations(query: string, limit = 5): Promise<PlaceResult[]> {
  const { data } = await apiClient.get<PlaceResult[]>('/weather/geocode', {
    params: { q: query, limit },
  });
  return data;
}

export async function fetchWeatherByCoordinates(
  latitude: number,
  longitude: number,
  locationName?: string
): Promise<SearchedWeather> {
  const { data } = await apiClient.get<SearchedWeather>('/weather/live-by-coords', {
    params: {
      latitude,
      longitude,
      location_name: locationName,
    },
  });
  return data;
}

// ── Data Quality ───────────────────────────────────────────────────────────────
export async function getDataQualityStats(): Promise<DataQualityStats> {
  const { data } = await apiClient.get<DataQualityStats>('/data-quality/stats');
  return data;
}

export async function getDataQualityEvents(params?: { limit?: number; event_type?: string }): Promise<DataQualityEvent[]> {
  const { data } = await apiClient.get<DataQualityEvent[]>('/data-quality/events', { params });
  return data;
}

// ── Agricultural Intelligence & Recommendations ──────────────────────────────
export async function getCropRecommendation(payload: import('../types').CropRecommendationRequest): Promise<import('../types').CropRecommendationResponse> {
  const { data } = await apiClient.post<import('../types').CropRecommendationResponse>('/recommendations/crop', payload);
  return data;
}

export async function getCropModelMetrics(): Promise<import('../types').CropModelMetrics> {
  const { data } = await apiClient.get<import('../types').CropModelMetrics>('/recommendations/crop/metrics');
  return data;
}

export async function getIrrigationRecommendation(
  payload: import('../types').IrrigationRecommendationRequest,
  lang?: string
): Promise<import('../types').IrrigationRecommendationResponse> {
  const { data } = await apiClient.post<import('../types').IrrigationRecommendationResponse>(
    '/recommendations/irrigation',
    payload,
    { params: lang ? { lang } : undefined }
  );
  return data;
}

export async function getFieldIrrigationRecommendation(
  fieldId: string,
  lang?: string
): Promise<import('../types').IrrigationRecommendationResponse> {
  const { data } = await apiClient.get<import('../types').IrrigationRecommendationResponse>(
    `/recommendations/irrigation/${fieldId}`,
    { params: lang ? { lang } : undefined }
  );
  return data;
}

// ── Sarvam AI Dynamic Language Integration ─────────────────────────────────────
export interface SarvamStatus {
  configured: boolean;
  base_url: string;
  translate_model: string;
  tts_model: string;
  stt_model: string;
  supported_languages: Array<{
    code: string;
    name: string;
    native: string;
    sarvam_code: string;
  }>;
}

export interface SarvamTranslationResult {
  translated_text: string;
  source_language: string;
  target_language: string;
  is_fallback: boolean;
  notice?: string;
}

export interface SarvamTTSResult {
  audio_base64: string | null;
  target_language_code: string;
  format?: string | null;
  fallback: boolean;
  text?: string;
}

export interface SarvamSTTResult {
  transcript: string;
  language_code: string;
  fallback: boolean;
  message?: string;
}

export async function getSarvamStatus(): Promise<SarvamStatus> {
  const { data } = await apiClient.get<SarvamStatus>('/sarvam/status');
  return data;
}

export async function translateDynamicText(
  text: string,
  targetLanguage: string,
  sourceLanguage: string = 'en'
): Promise<SarvamTranslationResult> {
  const { data } = await apiClient.post<SarvamTranslationResult>('/sarvam/translate', {
    text,
    target_language: targetLanguage,
    source_language: sourceLanguage,
  });
  return data;
}

export async function translateDynamicRecommendation(
  recommendation: import('../types').IrrigationRecommendationResponse,
  targetLanguage: string
): Promise<import('../types').IrrigationRecommendationResponse> {
  const { data } = await apiClient.post<import('../types').IrrigationRecommendationResponse>(
    '/sarvam/translate-recommendation',
    {
      recommendation,
      target_language: targetLanguage,
    }
  );
  return data;
}

export async function synthesizeSpeech(
  text: string,
  targetLanguage: string,
  speaker?: string
): Promise<SarvamTTSResult> {
  const { data } = await apiClient.post<SarvamTTSResult>('/sarvam/text-to-speech', {
    text,
    target_language: targetLanguage,
    speaker: speaker || undefined,
  });
  return data;
}

export async function transcribeAudio(
  audioBase64: string,
  languageCode?: string
): Promise<SarvamSTTResult> {
  const { data } = await apiClient.post<SarvamSTTResult>('/sarvam/speech-to-text-base64', {
    audio_base64: audioBase64,
    language_code: languageCode,
  });
  return data;
}

export interface AssistantChatResponse {
  answer: string;
  audio_base64?: string | null;
  language: string;
  field_id?: string | null;
  field_name?: string | null;
  crop_type?: string | null;
  suggestions: string[];
}

export async function askAssistant(
  message: string,
  language: string,
  fieldId?: string | null,
  includeAudio: boolean = true
): Promise<AssistantChatResponse> {
  const { data } = await apiClient.post<AssistantChatResponse>('/assistant/chat', {
    message,
    language,
    field_id: fieldId || null,
    include_audio: includeAudio,
  });
  return data;
}

export async function getAssistantGreeting(language: string): Promise<{
  greeting: string;
  language: string;
  suggestions: string[];
}> {
  const { data } = await apiClient.get('/assistant/greeting', {
    params: { lang: language },
  });
  return data;
}

// ── Irrigation Logs & History ──────────────────────────────────────────────────
export async function getIrrigationLogs(fieldId?: string): Promise<IrrigationLog[]> {
  const { data } = await apiClient.get<IrrigationLog[]>('/irrigation/logs', {
    params: fieldId ? { field_id: fieldId } : undefined,
  });
  return data;
}

export async function createIrrigationLog(payload: IrrigationLogCreate): Promise<IrrigationLog> {
  const { data } = await apiClient.post<IrrigationLog>('/irrigation/logs', payload);
  return data;
}

// ── PDF & CSV Reports ──────────────────────────────────────────────────────────
export async function getReportSummary(
  fieldId: string,
  options?: { startDate?: string; endDate?: string; lang?: string }
): Promise<ReportSummary> {
  const { data } = await apiClient.get<ReportSummary>(`/reports/fields/${fieldId}/summary`, {
    params: {
      start_date: options?.startDate || undefined,
      end_date: options?.endDate || undefined,
      lang: options?.lang || undefined,
    },
  });
  return data;
}

export async function downloadPdfReport(
  fieldId: string,
  options?: { startDate?: string; endDate?: string; lang?: string }
): Promise<void> {
  const response = await apiClient.get(`/reports/fields/${fieldId}/pdf`, {
    params: {
      lang: options?.lang || 'en',
      start_date: options?.startDate || undefined,
      end_date: options?.endDate || undefined,
    },
    responseType: 'blob',
  });

  const blob = new Blob([response.data], { type: 'application/pdf' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  const langSuffix = options?.lang || 'en';
  link.download = `irrigation_report_${fieldId}_${langSuffix}_${new Date().toISOString().slice(0, 10)}.pdf`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export async function downloadCsvReport(
  fieldId: string,
  options?: { startDate?: string; endDate?: string }
): Promise<void> {
  const response = await apiClient.get(`/reports/fields/${fieldId}/csv`, {
    params: {
      start_date: options?.startDate || undefined,
      end_date: options?.endDate || undefined,
    },
    responseType: 'blob',
  });

  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `irrigation_report_${fieldId}_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

// ── Alerts & Multi-Channel Notifications API ─────────────────────────────────

export async function getAlerts(params?: {
  field_id?: string;
  sensor_id?: string;
  alert_type?: string;
  severity?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<Alert[]> {
  const { data } = await apiClient.get<Alert[]>('/alerts', { params });
  return data;
}

export async function getAlert(alertId: number): Promise<Alert> {
  const { data } = await apiClient.get<Alert>(`/alerts/${alertId}`);
  return data;
}

export async function acknowledgeAlert(alertId: number): Promise<Alert> {
  const { data } = await apiClient.patch<Alert>(`/alerts/${alertId}/acknowledge`);
  return data;
}

export async function resolveAlert(alertId: number): Promise<Alert> {
  const { data } = await apiClient.patch<Alert>(`/alerts/${alertId}/resolve`);
  return data;
}

export async function dispatchNotificationTest(
  payload: NotificationTestPayload
): Promise<any> {
  const { data } = await apiClient.post('/alerts/notify', payload);
  return data;
}

// ── Automated Irrigation & Telemetry Reports ──────────────────────────────────
export async function getReportsSummary(): Promise<ReportsSummary> {
  const { data } = await apiClient.get<ReportsSummary>('/reports/summary');
  return data;
}

export async function getDailyReports(params?: {
  days?: number;
  field_id?: string;
}): Promise<DailyReportItem[]> {
  const { data } = await apiClient.get<DailyReportItem[]>('/reports/daily', { params });
  return data;
}

// ── Irrigation Schedules (Milestone 3) ────────────────────────────────────────
export async function getIrrigationSchedules(params?: {
  field_id?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}): Promise<IrrigationSchedule[]> {
  const { data } = await apiClient.get<IrrigationSchedule[]>('/irrigation/schedules', { params });
  return data;
}

export async function createIrrigationSchedule(
  payload: IrrigationScheduleCreate
): Promise<IrrigationSchedule> {
  const { data } = await apiClient.post<IrrigationSchedule>('/irrigation/schedules', payload);
  return data;
}

export async function updateIrrigationSchedule(
  scheduleId: string,
  payload: IrrigationScheduleUpdate
): Promise<IrrigationSchedule> {
  const { data } = await apiClient.put<IrrigationSchedule>(`/irrigation/schedules/${scheduleId}`, payload);
  return data;
}

export async function deleteIrrigationSchedule(scheduleId: string): Promise<void> {
  await apiClient.delete(`/irrigation/schedules/${scheduleId}`);
}

export async function generateIrrigationSchedule(fieldId: string): Promise<IrrigationSchedule> {
  const { data } = await apiClient.post<IrrigationSchedule>(`/irrigation/schedules/generate/${fieldId}`);
  return data;
}

export async function updateIrrigationScheduleStatus(
  scheduleId: string,
  status: 'pending' | 'completed' | 'skipped' | 'cancelled'
): Promise<IrrigationSchedule> {
  const { data } = await apiClient.patch<IrrigationSchedule>(
    `/irrigation/schedules/${scheduleId}/status`,
    { status }
  );
  return data;
}

// ── Farmer Dashboard & Intelligence (Milestone 3) ─────────────────────────────
export async function getFarmerDashboard(): Promise<FarmerDashboard> {
  const { data } = await apiClient.get<FarmerDashboard>('/farmers/me/dashboard');
  return data;
}

export async function getFarmAlerts(): Promise<FarmAlert[]> {
  const { data } = await apiClient.get<FarmAlert[]>('/farmers/me/alerts');
  return Array.isArray(data) ? data : [];
}

export async function getDigitalTwin(): Promise<DigitalTwinResponse> {
  const { data } = await apiClient.get<DigitalTwinResponse>('/intelligence/digital-twin');
  return data;
}

export async function getCropStress(fieldId?: string): Promise<CropStressResponse> {
  const { data } = await apiClient.get<CropStressResponse>('/intelligence/crop-stress', {
    params: fieldId ? { field_id: fieldId } : {},
  });
  return data;
}

export async function calculateWaterBudget(payload: {
  available_water_liters: number;
  horizon_days: number;
}): Promise<WaterBudgetResponse> {
  const { data } = await apiClient.post<WaterBudgetResponse>('/intelligence/water-budget', payload);
  return data;
}

// ── CSV Export Utilities ──────────────────────────────────────────────────────
export function downloadCsv(csvContent: string, filename: string): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function exportSchedulesToCsv(schedules: IrrigationSchedule[]): void {
  const headers = ['Schedule ID', 'Field ID', 'Recommended Date', 'Time', 'Duration (mins)', 'Water (Liters)', 'Priority', 'Reason', 'Status', 'Created At'];
  const rows = schedules.map((s) => [
    s.schedule_id,
    s.field_id,
    (s.recommended_date || '').split('T')[0],
    s.recommended_time,
    s.duration_minutes,
    s.water_quantity_liters,
    s.priority || 'normal',
    `"${(s.reason || '').replace(/"/g, '""')}"`,
    s.status,
    s.created_at || '',
  ]);
  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  downloadCsv(csv, `agripulse_schedules_${new Date().toISOString().split('T')[0]}.csv`);
}

export function exportWaterAnalyticsToCsv(analytics: WaterAnalytics): void {
  const summaryHeaders = ['Metric', 'Value (Liters)', 'Basis'];
  const summaryRows = [
    ['Daily Completed Schedule Volume Estimate', analytics.daily_schedule_volume_estimate_liters, analytics.volume_basis || 'unavailable'],
    ['Weekly Completed Schedule Volume Estimate', analytics.weekly_schedule_volume_estimate_liters, analytics.volume_basis || 'unavailable'],
    ['Monthly Completed Schedule Volume Estimate', analytics.monthly_schedule_volume_estimate_liters, analytics.volume_basis || 'unavailable'],
    ['Efficiency Score (%)', analytics.efficiency_score, 'Unavailable without measured delivered volume'],
    ['Estimated Traditional Flood Baseline', analytics.baseline_comparison.traditional_flood_liters, '50mm per completed cycle'],
    ['Completed Schedule Volume Estimate', analytics.baseline_comparison.completed_schedule_volume_estimate_liters, analytics.volume_basis || 'unavailable'],
    ['Estimated Water Saved', analytics.baseline_comparison.water_saved_liters, 'Model comparison; not measured savings'],
    ['Estimated Water Saved (%)', analytics.baseline_comparison.water_saved_percent, 'Model comparison; not measured savings'],
  ];

  const fieldHeaders = ['Field ID', 'Field Name', 'Completed Schedule Volume Estimate (L)', 'Planned Schedule Volume (L)'];
  const fieldRows = (analytics.field_breakdown || []).map((f) => [
    f.field_id,
    `"${f.field_name.replace(/"/g, '""')}"`,
    f.completed_schedule_volume_estimate_liters ?? '',
    f.planned_liters,
  ]);

  const csv = [
    '--- WATER CONSUMPTION SUMMARY ---',
    summaryHeaders.join(','),
    ...summaryRows.map((r) => r.join(',')),
    '',
    '--- FIELD WATER BREAKDOWN ---',
    fieldHeaders.join(','),
    ...fieldRows.map((r) => r.join(',')),
  ].join('\n');

  downloadCsv(csv, `agripulse_water_analytics_${new Date().toISOString().split('T')[0]}.csv`);
}



