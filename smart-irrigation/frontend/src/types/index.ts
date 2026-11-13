export interface Farmer {
  farmer_id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  preferred_language?: string | null;
  village?: string | null;
  district?: string | null;
  state?: string | null;
  age?: number | null;
  contact_method?: string | null;
  is_demo?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface FarmerCreate {
  farmer_id?: string;
  name: string;
  phone?: string;
  email?: string;
  preferred_language?: string;
  village?: string;
  district?: string;
  state?: string;
  age?: number;
  contact_method?: string;
}

export interface FarmerUpdate {
  name?: string;
  phone?: string;
  email?: string;
  preferred_language?: string;
  village?: string;
  district?: string;
  state?: string;
  age?: number;
  contact_method?: string;
}

export interface FarmerLoginPayload {
  email_or_phone: string;
  password: string;
}

export interface FarmerRegisterPayload {
  name: string;
  email: string;
  phone: string;
  password: string;
  preferred_language?: string;
  state?: string;
  district?: string;
  village?: string;
  age?: number;
  contact_method?: string;
  farm_name?: string;
  field_name?: string;
  area?: number;
  area_unit?: string;
  soil_type?: string;
  soil_ph?: number;
  irrigation_method?: string;
  pump_flow_rate_lpm?: number;
  crop_type?: string;
  crop_variety?: string;
  planting_date?: string;
  growth_stage?: string;
  latitude?: number;
  longitude?: number;
  location_name?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  farmer: Farmer;
}

export interface Field {
  field_id: string;
  farmer_id: string;
  name: string;
  location_name?: string | null;
  location?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  crop_type: string;
  area_hectares?: number | null;
  pump_flow_rate_lpm?: number | null;
  irrigation_method?: string | null;
  soil_type?: string | null;
  soil_ph?: number | null;
  is_demo?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface FieldCreate {
  field_id?: string;
  farmer_id?: string;
  name: string;
  location_name?: string;
  city?: string;
  state?: string;
  country?: string;
  latitude?: number;
  longitude?: number;
  crop_type: string;
  area_hectares?: number;
  pump_flow_rate_lpm?: number;
  irrigation_method?: string;
  soil_type?: string;
  soil_ph?: number;
}

export interface FieldUpdate {
  name?: string;
  farmer_id?: string;
  location_name?: string;
  city?: string;
  state?: string;
  country?: string;
  latitude?: number;
  longitude?: number;
  crop_type?: string;
  area_hectares?: number;
  pump_flow_rate_lpm?: number;
  irrigation_method?: string;
  soil_type?: string;
  soil_ph?: number;
}

export interface Crop {
  crop_id: string;
  field_id: string;
  crop_type: string;
  variety?: string | null;
  planting_date?: string | null;
  growth_stage?: string | null;
  notes?: string | null;
  is_demo?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CropCreate {
  crop_id?: string;
  field_id: string;
  crop_type: string;
  variety?: string;
  planting_date?: string;
  growth_stage?: string;
  notes?: string;
}

export interface CropPatch {
  crop_type?: string;
  variety?: string;
  planting_date?: string;
  growth_stage?: string;
  notes?: string;
  field_id?: string;
}

export interface Sensor {
  sensor_id: string;
  field_id: string;
  sensor_type: string;
  unit?: string | null;
  status: 'active' | 'inactive';
  connectivity_mode?: string | null;
  last_seen_at?: string | null;
  is_simulated?: boolean;
  is_demo?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SensorCreate {
  sensor_id?: string;
  field_id: string;
  sensor_type?: string;
  unit?: string;
  status?: string;
  is_simulated?: boolean;
}

export interface SensorUpdate {
  field_id?: string;
  sensor_type?: string;
  unit?: string;
  status?: string;
  is_simulated?: boolean;
}

export interface SensorReading {
  reading_id: number;
  sensor_id: string;
  field_id: string;
  timestamp: string;
  soil_moisture?: number | null;
  measurement_type: string;
  value?: number | null;
  unit?: string | null;
  quality_status: string;
  quality_flags?: string | null;
  temperature?: number | null;
  humidity?: number | null;
  soil_ph?: number | null;
  rainfall?: number | null;
  water_level?: number | null;
  flow_rate?: number | null;
  is_simulated: boolean;
  ingested_at: string;
}

export interface SensorReadingIn {
  sensor_id: string;
  field_id?: string;
  timestamp?: string;
  soil_moisture?: number;
  measurement_type?: string;
  value?: number;
  unit?: string;
  temperature?: number;
  humidity?: number;
  soil_ph?: number;
  rainfall?: number;
  water_level?: number;
  flow_rate?: number;
  is_simulated?: boolean;
}

export interface WeatherData {
  weather_id: number;
  field_id: string;
  timestamp: string;    // provider observation time (UTC)
  fetched_at?: string | null;  // when our backend called the API
  temperature: number;
  humidity: number;
  rainfall: number;
  wind_speed?: number | null;
  condition?: string | null;
  source: string;
  is_mock: boolean;
}

export interface PlaceResult {
  name: string;
  state?: string | null;
  country?: string | null;
  latitude: number;
  longitude: number;
  label: string;
}

export interface WeatherFetchResponse {
  status: string;
  weather: WeatherData;
  mock: boolean;
  requested_coordinates?: { latitude: number; longitude: number } | null;
  provider_coordinates?: { latitude: number; longitude: number } | null;
  provider_location?: string | null;
}

export interface SearchedWeather {
  latitude: number;
  longitude: number;
  location_name?: string | null;
  timestamp: string;
  fetched_at: string;
  temperature: number;
  humidity: number;
  rainfall: number;
  wind_speed?: number | null;
  condition?: string | null;
  source: string;
  is_mock: boolean;
  provider_coordinates?: { latitude: number; longitude: number } | null;
  provider_location?: string | null;
}

export interface DataQualityStats {
  readings_stored: number;
  valid_readings: number;
  simulated_readings: number;
  out_of_order_stored: number;
  ingestion_failures: number;
  invalid_readings: number;
  missing_value_count: number;
  duplicate_count: number;
  out_of_range_count: number;
  invalid_timestamp_count: number;
  weather_observations: number;
  weather_mock_observations: number;
  weather_ingestion_failures: number;
  events_by_type: Record<string, number>;
  events_by_source: Record<string, number>;
  notes: string[];
}

export interface DataQualityEvent {
  event_id: number;
  event_type: string;
  source: string;
  sensor_id?: string | null;
  field_id?: string | null;
  message: string;
  details?: string | null;
  created_at: string;
}

export interface SystemStatus {
  backend: {
    ok: boolean;
    version: string;
    environment: string;
  };
  database: {
    ok: boolean;
    error?: string | null;
    url: string;
  };
  timescaledb: {
    available: boolean;
    version?: string | null;
    hypertables: string[];
    reason?: string | null;
  };
  weather: {
    configured: boolean;
    mock_mode: boolean;
    provider: string;
  };
  mqtt: {
    enabled: boolean;
    configured: boolean;
    connected: boolean;
    broker?: string | null;
    topic?: string | null;
    last_error?: string | null;
  };
  docs: string;
}

export interface DashboardSummary {
  farmers: number;
  fields: number;
  sensors: number;
  active_sensors: number;
  active_alerts_count?: number;
  recent_alerts?: Alert[];
  readings_stored: number;
  valid_readings: number;
  simulated_readings: number;
  ingestion_failures: number;
  weather_observations: number;
  timescale_active: boolean;
  latest_readings: SensorReading[];
  latest_weather?: WeatherData | null;
}

export interface CropCandidate {
  crop: string;
  probability: number;
  confidence_pct: number;
}

export interface CropRecommendationRequest {
  N: number;
  P: number;
  K: number;
  temperature: number;
  humidity: number;
  ph: number;
  rainfall: number;
  soil_moisture?: number;
}

export interface CropRecommendationResponse {
  recommended_crop: string;
  confidence: number;
  top_candidates: Array<{ crop: string; probability: number; confidence_pct: number }>;
  agronomic_explanation: string;
  input_parameters: Record<string, number>;
  model_metadata: Record<string, any>;
  limitations: string;
}

export interface CropModelMetrics {
  model_name: string;
  algorithm: string;
  train_samples: number;
  test_samples: number;
  test_accuracy: number;
  macro_f1: number;
  feature_names: string[];
  feature_importances: Record<string, number>;
  trained_at: string;
  notes: string[];
}

export interface IrrigationRecommendationRequest {
  field_id?: string;
  crop_type?: string;
  growth_stage?: string;
  soil_moisture?: number;
  temperature?: number;
  recent_rainfall_mm?: number;
  forecast_rainfall_mm?: number;
}

export type IrrigationScheduleAction = 'IRRIGATE' | 'DEFER' | 'NO_IRRIGATION_NEEDED' | 'WITHHELD';

export interface IrrigationVolume {
  litres: number;
  cubic_metres: number;
  area_hectares: number;
  basis: string;
}

export type AlertLevel = 'NONE' | 'INFO' | 'WARNING' | 'EMERGENCY';

export interface IrrigationAlert {
  code: string;
  level: AlertLevel;
  title: string;
  message: string;
  recommended_action: string;
}

export interface IrrigationAlerts {
  level: AlertLevel;
  is_emergency: boolean;
  alerts: IrrigationAlert[];
  generated_at_utc?: string;
  disclaimer?: string;
}

export interface MLPrediction {
  available: boolean;
  reason?: string | null;
  irrigate?: boolean | null;
  probability?: number | null;
  threshold?: number | null;
  depth_mm?: number | null;
  model_name?: string | null;
  model_version?: string | null;
  warnings?: string[];
  fallback?: string;
  overridden_by?: string;
}

export interface IrrigationPlanSlot {
  window: string; // IMMEDIATE | MORNING | EVENING
  start_local: string;
  end_local: string;
  duration_min: number;
  depth_mm: number;
  volume_litres?: number;
}

export interface IrrigationPlan {
  status: 'SCHEDULED' | 'NO_PLAN';
  slots: IrrigationPlanSlot[];
  emergency: boolean;
  total_depth_mm: number;
  total_duration_min: number;
  rate_mm_per_hour: number | null;
  rate_assumed: boolean | null;
  warnings: string[];
  reason?: string | null;
  reevaluate_at_utc?: string | null;
}

/** Weather-aware scheduling decision (backend: IrrigationSchedule.to_dict()). This is the final decision. */
export interface IrrigationRecommendationSchedule {
  field_id: string | null;
  action: IrrigationScheduleAction;
  predicted_irrigation_mm: number | null;
  recommended_irrigation_mm: number | null;
  unit: string;
  volume: IrrigationVolume | null;
  reasons: string[];
  reason_codes: string[];
  warnings: string[];
  reevaluate_after_hours: number | null;
  weather_context?: Record<string, any>;
  thresholds?: Record<string, number>;
  assumptions?: string[];
  disclaimer?: string;
  generated_at_utc?: string;
  translated_reasons?: string[];
  translated_warnings?: string[];
  translated_assumptions?: string[];
  translated_disclaimer?: string;
}

export interface IrrigationScheduleInput {
  predicted_irrigation_mm: number | null;
  unit: string;
  source: string;
  is_ml_prediction: boolean;
  recommendation_engine?: string | null;
  note: string;
}

export interface SchedulingRecommendation {
  recommended_irrigation_date: string | null;
  recommended_time_window: string | null;
  start_time: string | null;
  end_time: string | null;
  estimated_duration_minutes: number | null;
  estimated_duration_formatted: string;
  pump_flow_rate_lpm: number | null;
  flow_rate_status: 'configured' | 'not_configured';
  field_area_hectares: number | null;
  predicted_water_depth_mm: number | null;
  water_volume_litres: number | null;
  reason: string;
  disclaimer: string;
}

export interface IrrigationRecommendationResponse {
  action: 'IRRIGATE_IMMEDIATELY' | 'IRRIGATE_LIGHT' | 'MAINTAIN_MONITORING' | 'DEFER_DUE_TO_RAIN';
  recommended_water_mm: number;
  urgency: 'HIGH' | 'MODERATE' | 'LOW' | 'NONE';
  reason: string;
  factors_evaluated: Record<string, any>;
  recommendation_engine: string;
  sensor_freshness: string;
  limitations: string;
  // Additive scheduling fields. Optional: absent/null when no registered field was available (see scheduling_note).
  irrigation_schedule?: IrrigationRecommendationSchedule | null;
  schedule_input?: IrrigationScheduleInput | null;
  scheduling_note?: string | null;
  scheduling_recommendation?: SchedulingRecommendation | null;
  ml_prediction?: MLPrediction | null;
  irrigation_plan?: IrrigationPlan | null;
  alerts?: IrrigationAlerts | null;
  // Multilingual translation fields (Sarvam AI integration)
  translated_reason?: string | null;
  translated_action?: string | null;
  translated_urgency?: string | null;
  translated_limitations?: string | null;
  translated_scheduling_note?: string | null;
  language?: string | null;
  language_code?: string | null;
}

export interface IrrigationLog {
  log_id: number;
  field_id: string;
  timestamp: string;
  water_depth_mm: number;
  water_volume_litres?: number | null;
  duration_minutes?: number | null;
  flow_rate_lpm?: number | null;
  source: string;
  notes?: string | null;
  created_at: string;
}

export interface IrrigationLogCreate {
  field_id: string;
  timestamp?: string;
  water_depth_mm: number;
  duration_minutes?: number;
  flow_rate_lpm?: number;
  source?: string;
  notes?: string;
}

export interface ReportSummary {
  field_id: string;
  field_name: string;
  area_hectares: number | null;
  pump_flow_rate_lpm: number | null;
  irrigation_method: string | null;
  farmer_name: string;
  crop_name: string;
  growth_stage: string;
  sensor_readings_count: number;
  weather_records_count: number;
  irrigation_records_count: number;
  ml_water_requirement_mm: number | null;
  water_volume_litres: number | null;
  recommended_date: string | null;
  recommended_time_window: string | null;
  estimated_duration_minutes: number | null;
  scheduling_reason: string | null;
  disclaimer: string | null;
  filter: {
    start_date: string | null;
    end_date: string | null;
    lang: string;
  };
}

// ── Alert Engine & Notification Interfaces ─────────────────────────────────────
export interface Alert {
  alert_id: number;
  field_id: string;
  sensor_id: string;
  alert_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'open' | 'acknowledged' | 'resolved';
  source: string;
  message: string;
  recommended_action?: string | null;
  value?: number | null;
  threshold?: number | null;
  occurrence_count: number;
  created_at: string;
  last_seen_at: string;
  acknowledged_at?: string | null;
  acknowledged_by_user_id?: number | null;
  resolved_at?: string | null;
}

export interface ReportsSummary {
  total_alerts: number;
  open_alerts: number;
  acknowledged_alerts: number;
  resolved_alerts: number;
  critical_alerts: number;
  high_alerts: number;
  total_fields: number;
  high_risk_fields: number;
  average_soil_moisture?: number | null;
  water_usage_liters_today: number;
  estimated_water_saved_percent: number;
  forecast_24h_demand_mm: number;
  system_health_status: 'OPTIMAL' | 'ATTENTION_REQUIRED' | 'CRITICAL';
  generated_at: string;
}

export interface DailyReportItem {
  date: string;
  avg_moisture: number;
  avg_temperature: number;
  total_rainfall_mm: number;
  irrigation_water_used_liters: number;
  alerts_triggered: number;
}

export interface NotificationTestPayload {
  channel: 'SMS' | 'WHATSAPP' | 'EMAIL' | 'WEB_PUSH';
  recipient: string;
  title?: string;
  message: string;
}

export interface ReadingSnapshot {
  timestamp: string;
  soil_moisture?: number | null;
  temperature?: number | null;
  humidity?: number | null;
  rainfall?: number | null;
  is_simulated: boolean;
}

export interface DigitalTwinField {
  field_id: string;
  name: string;
  crop_type: string;
  area_hectares?: number | null;
  health: 'healthy' | 'moderate' | 'critical' | 'unknown';
  health_reason: string;
  latest_reading?: ReadingSnapshot | null;
  moisture_change?: number | null;
  irrigation_status: string;
  pending_water_liters: number;
}

export interface DigitalTwinResponse {
  generated_at: string;
  live_fields: number;
  fields_without_telemetry: number;
  fields: DigitalTwinField[];
}

export interface CropStressField {
  field_id: string;
  field_name: string;
  risk_score: number;
  risk_level: 'Low' | 'Moderate' | 'High' | 'Critical';
  data_available: boolean;
  reasons: string[];
  recommended_actions: string[];
  latest_reading?: ReadingSnapshot | null;
}

export interface CropStressResponse {
  generated_at: string;
  fields: CropStressField[];
}

export interface WaterAllocation {
  field_id: string;
  field_name: string;
  priority: string;
  moisture_percent?: number | null;
  estimated_demand_liters: number;
  allocated_liters: number;
  shortage_liters: number;
  reason: string;
}

export interface WaterBudgetRequest {
  available_water_liters: number;
  horizon_days?: number;
}

export interface WaterBudgetResponse {
  generated_at: string;
  available_water_liters: number;
  estimated_demand_liters: number;
  allocated_water_liters: number;
  remaining_water_liters: number;
  shortage_liters: number;
  savings_vs_full_demand_percent: number;
  assumptions: string[];
  allocations: WaterAllocation[];
}

export interface IrrigationSchedule {
  schedule_id: string;
  field_id: string;
  recommended_date: string;
  recommended_time: string;
  duration_minutes: number;
  water_quantity_liters: number;
  priority?: string | null;
  reason?: string | null;
  status: 'pending' | 'completed' | 'skipped' | 'cancelled';
  created_at: string;
  updated_at: string;
}

export interface IrrigationScheduleCreate {
  field_id: string;
  recommended_date: string;
  recommended_time: string;
  duration_minutes: number;
  water_quantity_liters: number;
  priority?: string;
  reason?: string;
}

export interface IrrigationScheduleUpdate {
  recommended_date?: string;
  recommended_time?: string;
  duration_minutes?: number;
  water_quantity_liters?: number;
  priority?: string;
  reason?: string;
  status?: 'pending' | 'completed' | 'skipped' | 'cancelled';
}

export interface BaselineComparison {
  traditional_flood_liters?: number | null;
  actual_liters?: number | null;
  completed_schedule_volume_estimate_liters?: number | null;
  water_saved_liters?: number | null;
  water_saved_percent?: number | null;
  is_estimated?: boolean;
  baseline_description: string;
}

export interface FieldWaterUsage {
  field_id: string;
  field_name: string;
  actual_liters?: number | null;
  completed_schedule_volume_estimate_liters?: number | null;
  planned_liters: number;
}

export interface FieldCondition {
  field_id: string;
  action: 'IRRIGATE_IMMEDIATELY' | 'IRRIGATE_LIGHT' | 'MAINTAIN_MONITORING' | 'DEFER_DUE_TO_RAIN' | 'NO_SENSOR_DATA';
  urgency: 'HIGH' | 'MODERATE' | 'LOW' | 'NONE';
  reason: string;
  soil_moisture?: number | null;
  sensor_timestamp?: string | null;
  is_simulated?: boolean;
}

export interface WaterAnalytics {
  daily_consumption_liters?: number | null;
  weekly_consumption_liters?: number | null;
  monthly_consumption_liters?: number | null;
  daily_schedule_volume_estimate_liters?: number | null;
  weekly_schedule_volume_estimate_liters?: number | null;
  monthly_schedule_volume_estimate_liters?: number | null;
  volume_basis?: 'completed_schedule_estimates' | 'unavailable';
  efficiency_score?: number | null;
  field_breakdown: FieldWaterUsage[];
  baseline_comparison: BaselineComparison;
}

export interface FarmAlert {
  id: string;
  type: 'drought_risk' | 'low_moisture' | 'excess_moisture' | 'heavy_rainfall' | 'sensor_offline' | 'schedule_reminder' | 'schedule_completed' | 'over_irrigation' | 'weather_alert';
  severity: 'critical' | 'warning' | 'info';
  title: string;
  message: string;
  field_id?: string;
  field_name?: string;
  recommended_action?: string;
  timestamp: string;
  read?: boolean;
}

export interface FarmerDashboard {
  farmer_name?: string;
  farmer_email?: string;
  total_fields?: number;
  fields_needing_irrigation?: number;
  field_conditions?: FieldCondition[];
  average_soil_moisture?: number;
  total_water_used_liters?: number | null;
  completed_schedule_volume_estimate_liters?: number | null;
  weather_summary?: {
    temperature?: number;
    humidity?: number;
    rainfall?: number;
    wind_speed?: number | null;
    condition?: string | null;
    source?: string | null;
    is_mock?: boolean | null;
    timestamp?: string;
  } | null;
  water_analytics?: WaterAnalytics | null;
}


