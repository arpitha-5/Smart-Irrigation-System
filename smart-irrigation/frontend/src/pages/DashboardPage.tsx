import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  MapPin,
  Cpu,
  Droplets,
  CloudRain,
  ShieldAlert,
  Sparkles,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  AlertTriangle,
  Database,
  Mic,
  UserCheck,
  Compass,
  Bell,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';
import { getDashboardSummary, getSensorReadings, seedDemoData } from '../services/api';
import type { DashboardSummary, SensorReading } from '../types';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { LanguageSelector } from '../components/common/LanguageSelector';
import { VoicePlayer } from '../components/common/VoicePlayer';

export const DashboardPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { farmer, isAuthenticated } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [readings, setReadings] = useState<SensorReading[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [sumData, readData] = await Promise.all([
        getDashboardSummary(),
        getSensorReadings({ limit: 30 }),
      ]);
      setSummary(sumData);
      setReadings(readData);
    } catch (err: any) {
      setError(err?.message || 'Failed to load dashboard metrics from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSeed = async () => {
    if (!window.confirm('Load sample simulated demo data for UI evaluation? All records are explicitly labelled is_demo/is_simulated.')) {
      return;
    }
    setSeeding(true);
    try {
      await seedDemoData();
      await fetchData();
    } catch (err: any) {
      alert('Failed to seed demo data: ' + err.message);
    } finally {
      setSeeding(false);
    }
  };

  const chartData = [...readings].reverse().map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    moisture: r.soil_moisture ?? (r.measurement_type === 'soil_moisture' ? r.value : null),
    temperature:
      r.temperature !== null && r.temperature !== undefined
        ? r.temperature
        : r.measurement_type === 'temperature'
        ? r.value
        : null,
    sensorId: r.sensor_id,
  }));

  const hasTemperatureData = chartData.some((d) => d.temperature !== null && d.temperature !== undefined);
  const hasMoistureData = chartData.some((d) => d.moisture !== null && d.moisture !== undefined);
  const hasData = summary && (summary.farmers > 0 || (summary.readings_stored ?? 0) > 0);

  const activeAlertCount = summary?.active_alerts_count ?? 0;
  const recentAlerts = summary?.recent_alerts || [];

  // Dynamic alert summary text to be voiced in current language
  const alertSpeechText = activeAlertCount > 0
    ? `${activeAlertCount} active field alert${activeAlertCount > 1 ? 's' : ''}: ${recentAlerts.map(a => `${a.severity.toUpperCase()} alert on field ${a.field_id}: ${a.message}`).join('. ')}`
    : summary && summary.ingestion_failures > 0
    ? `${t('dashboard.recentAlerts', 'Active Alerts')}: ${summary.ingestion_failures} ${t('alerts.sensorStale', 'sensor telemetry anomalies detected. Please check field probes.')}`
    : `${t('dashboard.noAlerts', 'All field parameters are within optimal operating thresholds. No critical drought alerts.')}`;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t('dashboard.title', 'Agricultural Overview')}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {t('dashboard.subtitle', 'Real-time telemetry, TimescaleDB hypertable aggregation, and field water monitoring.')}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {/* Farmer Voice & Chat Assistant Button */}
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('open-agripulse-assistant'))}
            className="inline-flex items-center space-x-2 px-3.5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
            title="Ask question by voice or chat"
          >
            <Mic className="w-4 h-4 text-emerald-200" />
            <span>{t('dashboard.askVoiceAssistant', 'AI Voice & Chat Assistant')}</span>
          </button>

          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-600' : ''}`} />
            <span>{t('common.refresh', 'Refresh')}</span>
          </button>
        </div>
      </div>

      {/* Logged-in Farmer Personalized Banner */}
      {isAuthenticated && farmer && (
        <div className="dashboard-welcome relative overflow-hidden rounded-2xl bg-emerald-800 text-white p-5 sm:p-6 shadow-sm border border-emerald-700">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 text-xs font-semibold">
                <UserCheck className="w-3.5 h-3.5" />
                <span>{t('auth.verifiedFarmer', 'Verified Farmer Account')}</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight text-white flex items-center gap-2">
                <span>{t('dashboard.welcomeBack', 'Welcome back,')} {farmer.name}!</span>
                <span className="text-2xl">🌾</span>
              </h2>
              <p className="text-xs sm:text-sm text-emerald-100 flex flex-wrap items-center gap-x-3 gap-y-1">
                {(farmer.village || farmer.district || farmer.state) && (
                  <span className="inline-flex items-center space-x-1">
                    <MapPin className="w-3.5 h-3.5 text-emerald-300" />
                    <span>
                      {[farmer.village, farmer.district, farmer.state].filter(Boolean).join(', ')}
                    </span>
                  </span>
                )}
                {farmer.phone && (
                  <span className="text-emerald-200/80">
                    • 📱 {farmer.phone}
                  </span>
                )}
                <span className="text-emerald-200/80">
                  • 🌐 {farmer.preferred_language?.toUpperCase() || 'EN'}
                </span>
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Link
                to="/recommendations"
                className="inline-flex items-center space-x-2 px-4 py-2 bg-white text-emerald-800 hover:bg-emerald-50 font-bold text-xs rounded-xl shadow-xs transition-colors"
              >
                <Sparkles className="w-4 h-4 text-emerald-600" />
                <span>{t('dashboard.getAdvisory', 'Check Irrigation Advisory')}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/alerts"
                className="inline-flex items-center space-x-2 px-3.5 py-2 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-300/40 text-amber-100 font-medium text-xs rounded-xl transition-colors"
              >
                <Bell className="w-3.5 h-3.5 text-amber-300" />
                <span>{t('nav.alerts', 'Alerts & Reports')}</span>
              </Link>
              <Link
                to="/fields"
                className="inline-flex items-center space-x-2 px-3.5 py-2 bg-emerald-900/50 hover:bg-emerald-900/80 border border-emerald-400/30 text-white font-medium text-xs rounded-xl transition-colors"
              >
                <Compass className="w-3.5 h-3.5 text-emerald-200" />
                <span>{t('nav.fields', 'My Fields')}</span>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Prominent Farmer Language Selector Banner */}
      <LanguageSelector variant="prominent" />

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchData}
            className="text-xs font-semibold underline hover:no-underline cursor-pointer"
          >
            {t('common.refresh', 'Retry')}
          </button>
        </div>
      )}

      {/* Empty State with Demo Seeding CTA */}
      {!loading && !hasData && !error && (
        <div className="bg-white border-2 border-dashed border-emerald-200 rounded-2xl p-10 text-center max-w-2xl mx-auto my-8">
          <div className="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-bold text-slate-900 mb-2">No Agricultural Records Found</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
            The database is currently clean and ready. You can register your own farmers, fields, and sensors, or load a development-only simulated demo dataset.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              onClick={handleSeed}
              disabled={seeding}
              className="inline-flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm px-5 py-2.5 rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              <span>{seeding ? t('common.loading', 'Generating...') : 'Load Simulated Demo Dataset'}</span>
            </button>
            <Link
              to="/signup"
              className="inline-flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-sm px-5 py-2.5 rounded-xl transition-colors"
            >
              <span>{t('auth.register', 'Register Farmer Account')}</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Farmer Profile */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              {t('auth.farmerProfile', 'Farmer Profile')}
            </span>
            <Users className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-base font-bold text-slate-900 truncate">
            {farmer?.name || (isAuthenticated ? 'Active Farmer' : t('auth.login', 'Sign In'))}
          </div>
          <Link to={isAuthenticated ? '/profile' : '/login'} className="mt-3 text-xs text-emerald-600 hover:text-emerald-700 font-medium inline-flex items-center space-x-1">
            <span>{isAuthenticated ? t('auth.viewProfile', 'View profile & settings') : t('auth.login', 'Sign in to account')}</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {/* Fields */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              {t('dashboard.activeFields', 'Monitored Fields')}
            </span>
            <MapPin className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.fields ?? '—'}</div>
          <Link to="/fields" className="mt-3 text-xs text-emerald-600 hover:text-emerald-700 font-medium inline-flex items-center space-x-1">
            <span>{t('nav.fields', 'View fields & crops')}</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {/* Active Sensors */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              {t('dashboard.activeSensors', 'Active Sensors')}
            </span>
            <Cpu className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-slate-900">{summary?.active_sensors ?? '—'}</span>
            <span className="text-xs text-slate-400">/ {summary?.sensors ?? '—'} {t('common.all', 'total')}</span>
          </div>
          <Link to="/sensors" className="mt-3 text-xs text-emerald-600 hover:text-emerald-700 font-medium inline-flex items-center space-x-1">
            <span>{t('nav.sensors', 'Sensor telemetry')}</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {/* Readings Stored */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              {t('dashboard.dataPoints', 'Readings Ingested')}
            </span>
            <Droplets className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.readings_stored ?? '—'}</div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-emerald-600 font-medium">{summary?.valid_readings ?? 0} valid</span>
            <span className="text-slate-400">{summary?.simulated_readings ?? 0} simulated</span>
          </div>
        </div>
      </div>

      {/* Field Alerts & Audio Readout Card */}
      <div className={`p-5 rounded-2xl border shadow-xs transition-all ${
        activeAlertCount > 0 
          ? 'bg-rose-50/60 border-rose-200' 
          : 'bg-white border-slate-200/80'
      }`}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              activeAlertCount > 0 ? 'bg-rose-100 text-rose-600' : 'bg-emerald-50 text-emerald-600'
            }`}>
              {activeAlertCount > 0 ? <AlertTriangle className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  {t('dashboard.recentAlerts', 'Active Alerts & Field Notifications')}
                </span>
                {activeAlertCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-600 text-white animate-pulse">
                    {activeAlertCount} {activeAlertCount === 1 ? 'Alert' : 'Alerts'}
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-800 font-medium mt-0.5">
                {activeAlertCount > 0
                  ? `${activeAlertCount} active environmental or equipment risk condition${activeAlertCount > 1 ? 's' : ''} require attention.`
                  : t('dashboard.noAlerts', 'All field parameters are within optimal operating thresholds. No critical drought alerts.')}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 shrink-0">
            <VoicePlayer
              text={alertSpeechText}
              label={t('dashboard.listenToAlerts', 'Listen to Alerts')}
            />
            <Link
              to="/alerts"
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl transition-colors ${
                activeAlertCount > 0
                  ? 'bg-rose-600 hover:bg-rose-700 text-white shadow-xs'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              <Bell className="w-3.5 h-3.5" />
              <span>{activeAlertCount > 0 ? `Manage Alerts (${activeAlertCount})` : 'Alerts History'}</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>

        {/* If there are active alerts, show the list directly inside the card */}
        {activeAlertCount > 0 && recentAlerts.length > 0 && (
          <div className="mt-4 pt-4 border-t border-rose-200/60 space-y-2">
            {recentAlerts.map((alt) => (
              <div
                key={alt.alert_id}
                className="bg-white/90 p-3 rounded-xl border border-rose-100 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-2xs"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                      String(alt.severity).toUpperCase() === 'CRITICAL'
                        ? 'bg-rose-100 text-rose-800'
                        : String(alt.severity).toUpperCase() === 'HIGH'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-blue-100 text-blue-800'
                    }`}>
                      {alt.severity}
                    </span>
                    <span className="text-xs font-bold text-slate-800">
                      Field: {alt.field_id} {alt.sensor_id ? `• Sensor: ${alt.sensor_id}` : ''}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {alt.created_at ? new Date(alt.created_at).toLocaleTimeString() : ''}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700">{alt.message}</p>
                  {alt.recommended_action && (
                    <p className="text-[11px] text-emerald-700 font-medium">
                      💡 Action: {alt.recommended_action}
                    </p>
                  )}
                </div>
                <Link
                  to="/alerts"
                  className="shrink-0 text-xs font-semibold text-rose-700 hover:text-rose-900 underline"
                >
                  Resolve &rarr;
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Secondary Status Row: TimescaleDB & Weather */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* TimescaleDB Status Card */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${summary?.timescale_active ? 'bg-purple-50 text-purple-600' : 'bg-slate-100 text-slate-600'}`}>
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Time-Series Engine</div>
              <div className="text-sm font-bold text-slate-800">
                {summary?.timescale_active ? 'TimescaleDB Hypertables Active' : 'Plain PostgreSQL Tables'}
              </div>
            </div>
          </div>
          <Link to="/status" className="text-xs font-semibold text-emerald-600 hover:text-emerald-700">
            Details &rarr;
          </Link>
        </div>

        {/* Latest Weather Card */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <CloudRain className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                {t('weather.conditions', 'Latest Weather')}
              </div>
              <div className="text-sm font-bold text-slate-800">
                {summary?.latest_weather
                  ? `${summary.latest_weather.temperature}°C, ${summary.latest_weather.humidity}% RH`
                  : 'No observations yet'}
              </div>
            </div>
          </div>
          <Link to="/weather" className="text-xs font-semibold text-emerald-600 hover:text-emerald-700">
            {t('nav.weather', 'Weather')} &rarr;
          </Link>
        </div>

        {/* Data Quality & Failures */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${summary && summary.ingestion_failures > 0 ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'}`}>
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                {t('nav.dataQuality', 'Data Quality Pipeline')}
              </div>
              <div className="text-sm font-bold text-slate-800">
                {summary ? `${summary.ingestion_failures} Anomalies Caught` : '0 Anomalies'}
              </div>
            </div>
          </div>
          <Link to="/data-quality" className="text-xs font-semibold text-emerald-600 hover:text-emerald-700">
            Audits &rarr;
          </Link>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Soil Moisture Chart */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">
                {t('dashboard.moistureTrend', 'Recent Volumetric Soil Moisture (%)')}
              </h3>
              <p className="text-xs text-slate-500">Target agricultural safety band: 20% - 50%</p>
            </div>
            <Link to="/readings" className="text-xs text-emerald-600 hover:text-emerald-700 font-medium">
              {t('common.all', 'View all')}
            </Link>
          </div>
          <div className="h-64 w-full">
            {hasMoistureData ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="moistureGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '12px', fontSize: '12px' }}
                    formatter={(val: any) => [`${val}%`, 'Soil Moisture']}
                  />
                  <Area type="monotone" dataKey="moisture" stroke="#10b981" strokeWidth={2.5} fillOpacity={1} fill="url(#moistureGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-xs text-slate-400 space-y-1">
                <span>No volumetric soil moisture readings recorded yet.</span>
                <span className="text-[11px] text-slate-300">Register a soil moisture sensor or load demo data.</span>
              </div>
            )}
          </div>
        </div>

        {/* Ambient Temperature Chart */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">
                {t('weather.temperature', 'Temperature Telemetry (°C)')}
              </h3>
              <p className="text-xs text-slate-500">Multi-parameter sensor observations</p>
            </div>
            <Link to="/readings" className="text-xs text-emerald-600 hover:text-emerald-700 font-medium">
              {t('common.all', 'View all')}
            </Link>
          </div>
          <div className="h-64 w-full">
            {hasTemperatureData ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '12px', fontSize: '12px' }}
                    formatter={(val: any) => [`${val ?? 'N/A'}°C`, 'Temperature']}
                  />
                  <Line type="monotone" dataKey="temperature" stroke="#f59e0b" strokeWidth={2.5} connectNulls dot={{ r: 3, fill: '#f59e0b' }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-xs text-slate-400 space-y-1">
                <span>No temperature observations recorded yet.</span>
                <span className="text-[11px] text-slate-300">Connect a temperature telemetry sensor to view ambient trends.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Sensor Telemetry Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-slate-900 text-sm">
              {t('dashboard.dataPoints', 'Latest Ingested Readings')}
            </h3>
            <p className="text-xs text-slate-500">Verified through ingestion validation pipeline</p>
          </div>
          <Link
            to="/readings"
            className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center space-x-1"
          >
            <span>{t('nav.readings', 'Full History Table')}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">{t('sensors.sensorId', 'Sensor ID')}</th>
                <th className="py-3 px-4">{t('fields.fieldId', 'Field ID')}</th>
                <th className="py-3 px-4">{t('dashboard.averageMoisture', 'Moisture (%)')}</th>
                <th className="py-3 px-4">{t('sensors.type', 'Type / Value')}</th>
                <th className="py-3 px-4">{t('common.status', 'Status')}</th>
                <th className="py-3 px-4">Origin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {readings.slice(0, 8).map((r) => (
                <tr key={r.reading_id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3 px-4 font-mono text-[11px] text-slate-600">
                    {new Date(r.timestamp).toLocaleString()}
                  </td>
                  <td className="py-3 px-4 font-medium text-slate-900">{r.sensor_id}</td>
                  <td className="py-3 px-4 text-slate-600">{r.field_id}</td>
                  <td className="py-3 px-4">
                    {r.soil_moisture !== null && r.soil_moisture !== undefined ? (
                      <span className="font-semibold text-emerald-700">{r.soil_moisture}%</span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    {r.measurement_type} {r.value !== null && r.value !== undefined ? `(${r.value} ${r.unit || ''})` : ''}
                  </td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                      {r.quality_status}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {r.is_simulated ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                        Simulated
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700">
                        Live / Telemetry
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {readings.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-slate-400">
                    No readings ingested yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
