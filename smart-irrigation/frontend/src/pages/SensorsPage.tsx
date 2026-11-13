import React, { useEffect, useState } from 'react';
import {
  Cpu,
  Plus,
  Search,
  Power,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  X,
  Droplets,
  Activity,
  Edit2,
  Sparkles,
  Thermometer,
  CloudRain,
  Wind,
  Info,
  Check,
} from 'lucide-react';
import {
  getSensors,
  getFields,
  createSensor,
  updateSensor,
  deleteSensor,
  setSensorStatus,
  getSensorReadings,
  ingestReading,
  getErrorMessage,
} from '../services/api';
import type { Sensor, SensorCreate, SensorUpdate, Field, SensorReading, SensorReadingIn } from '../types';
import { useLanguage } from '../context/LanguageContext';

export const SensorsPage: React.FC = () => {
  const { t } = useLanguage();
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [latestReadings, setLatestReadings] = useState<Record<string, SensorReading>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [fieldFilter, setFieldFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [viewingReadings, setViewingReadings] = useState<{ sensor: Sensor; readings: SensorReading[] } | null>(null);
  const [loadingReadings, setLoadingReadings] = useState(false);

  // Form state: Register Sensor
  const [formData, setFormData] = useState<SensorCreate>({
    field_id: '',
    sensor_type: 'soil_moisture',
    unit: '%',
    status: 'active',
    is_simulated: false,
  });

  // Form state: Log Telemetry Modal (ML Required Fields)
  const [telemetryModalSensor, setTelemetryModalSensor] = useState<Sensor | null>(null);
  const [telemetryData, setTelemetryData] = useState<{
    sensor_id: string;
    field_id: string;
    soil_moisture: string;
    temperature: string;
    humidity: string;
    rainfall: string;
    soil_ph: string;
    is_simulated: boolean;
  }>({
    sensor_id: '',
    field_id: '',
    soil_moisture: '28.5',
    temperature: '29.0',
    humidity: '62.0',
    rainfall: '0.0',
    soil_ph: '6.8',
    is_simulated: false,
  });

  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [snsData, fldData, recentReadings] = await Promise.all([
        getSensors(),
        getFields(),
        getSensorReadings({ limit: 200 }),
      ]);
      setSensors(snsData);
      setFields(fldData);

      // Map latest reading per sensor
      const latestMap: Record<string, SensorReading> = {};
      recentReadings.forEach((r) => {
        if (!latestMap[r.sensor_id]) {
          latestMap[r.sensor_id] = r;
        }
      });
      setLatestReadings(latestMap);

      if (fldData.length > 0 && !formData.field_id) {
        setFormData((prev) => ({ ...prev, field_id: fldData[0].field_id }));
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.field_id) return;
    try {
      setSubmitting(true);
      setError(null);
      await createSensor(formData);
      setSuccess('Sensor registered successfully.');
      setTimeout(() => setSuccess(null), 3000);
      setShowAddModal(false);
      setFormData({
        field_id: fields[0]?.field_id || '',
        sensor_type: 'soil_moisture',
        unit: '%',
        status: 'active',
        is_simulated: false,
      });
      await fetchData();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const openTelemetryModal = (sensor?: Sensor) => {
    const targetSensor = sensor || sensors[0];
    if (!targetSensor) {
      setError('Please register a sensor first before logging telemetry.');
      return;
    }
    const currentLatest = latestReadings[targetSensor.sensor_id];
    setTelemetryModalSensor(targetSensor);
    setTelemetryData({
      sensor_id: targetSensor.sensor_id,
      field_id: targetSensor.field_id,
      soil_moisture: currentLatest?.soil_moisture !== null && currentLatest?.soil_moisture !== undefined
        ? String(currentLatest.soil_moisture)
        : '28.0',
      temperature: currentLatest?.temperature !== null && currentLatest?.temperature !== undefined
        ? String(currentLatest.temperature)
        : '29.5',
      humidity: currentLatest?.humidity !== null && currentLatest?.humidity !== undefined
        ? String(currentLatest.humidity)
        : '64.0',
      rainfall: currentLatest?.rainfall !== null && currentLatest?.rainfall !== undefined
        ? String(currentLatest.rainfall)
        : '0.0',
      soil_ph: currentLatest?.soil_ph !== null && currentLatest?.soil_ph !== undefined
        ? String(currentLatest.soil_ph)
        : '6.8',
      is_simulated: targetSensor.is_simulated || false,
    });
  };

  const handleLogTelemetry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!telemetryData.sensor_id || !telemetryData.field_id || !telemetryData.soil_moisture) {
      setError('Sensor, Field, and Soil Moisture are required.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const payload: SensorReadingIn = {
        sensor_id: telemetryData.sensor_id,
        field_id: telemetryData.field_id,
        soil_moisture: parseFloat(telemetryData.soil_moisture),
        temperature: telemetryData.temperature ? parseFloat(telemetryData.temperature) : undefined,
        humidity: telemetryData.humidity ? parseFloat(telemetryData.humidity) : undefined,
        rainfall: telemetryData.rainfall ? parseFloat(telemetryData.rainfall) : 0,
        soil_ph: telemetryData.soil_ph ? parseFloat(telemetryData.soil_ph) : undefined,
        value: parseFloat(telemetryData.soil_moisture),
        measurement_type: 'soil_moisture',
        unit: '%',
        is_simulated: telemetryData.is_simulated,
      };

      await ingestReading(payload);
      setSuccess(`Sensor telemetry logged successfully for ${telemetryData.sensor_id}! Complete ML prediction inputs are now available.`);
      setTimeout(() => setSuccess(null), 4000);
      setTelemetryModalSensor(null);
      await fetchData();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const applyPreset = (preset: 'optimal' | 'drought' | 'rain') => {
    if (preset === 'optimal') {
      setTelemetryData((prev) => ({
        ...prev,
        soil_moisture: '34.0',
        temperature: '26.5',
        humidity: '68.0',
        rainfall: '0.0',
      }));
    } else if (preset === 'drought') {
      setTelemetryData((prev) => ({
        ...prev,
        soil_moisture: '17.5',
        temperature: '36.0',
        humidity: '38.0',
        rainfall: '0.0',
      }));
    } else if (preset === 'rain') {
      setTelemetryData((prev) => ({
        ...prev,
        soil_moisture: '54.0',
        temperature: '23.0',
        humidity: '88.0',
        rainfall: '14.5',
      }));
    }
  };

  const handleToggleStatus = async (sensor: Sensor) => {
    const nextStatus = sensor.status === 'active' ? 'inactive' : 'active';
    try {
      setError(null);
      await setSensorStatus(sensor.sensor_id, nextStatus);
      setSuccess(`Sensor '${sensor.sensor_id}' status set to ${nextStatus}.`);
      setTimeout(() => setSuccess(null), 2500);
      await fetchData();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleDelete = async (sensor: Sensor) => {
    if (!window.confirm(`Delete sensor '${sensor.sensor_id}' and all associated historical readings?`)) return;
    try {
      setError(null);
      await deleteSensor(sensor.sensor_id);
      setSuccess(`Sensor '${sensor.sensor_id}' deleted.`);
      setTimeout(() => setSuccess(null), 3000);
      await fetchData();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleInspectReadings = async (sensor: Sensor) => {
    try {
      setLoadingReadings(true);
      setError(null);
      const readings = await getSensorReadings({ sensor_id: sensor.sensor_id, limit: 30 });
      setViewingReadings({ sensor, readings });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoadingReadings(false);
    }
  };

  const filteredSensors = sensors.filter((s) => {
    const matchesSearch =
      s.sensor_id.toLowerCase().includes(search.toLowerCase()) ||
      s.sensor_type.toLowerCase().includes(search.toLowerCase()) ||
      s.field_id.toLowerCase().includes(search.toLowerCase());
    const matchesField = fieldFilter ? s.field_id === fieldFilter : true;
    return matchesSearch && matchesField;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t('sensors.title', 'IoT Sensor Registry & Field Telemetry')}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {t('sensors.subtitle', 'Register field probes, configure ML-required environmental inputs, and monitor telemetry streams.')}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {sensors.length > 0 && (
            <button
              onClick={() => openTelemetryModal()}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <Droplets className="w-4 h-4 text-emerald-100" />
              <span>Log ML Telemetry</span>
            </button>
          )}
          <button
            onClick={() => setShowAddModal(true)}
            disabled={fields.length === 0}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors disabled:opacity-50 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>{t('sensors.addSensor', 'Register Sensor')}</span>
          </button>
          <button
            onClick={fetchData}
            className="p-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 rounded-xl transition-colors cursor-pointer"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* AI ML Irrigation Model Required Sensor Fields Guide */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-900 via-emerald-800 to-teal-900 text-white shadow-md border border-emerald-700/40">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-400/20 text-emerald-200 border border-emerald-400/30">
                AI Precision Irrigation
              </span>
              <span className="font-bold text-sm text-white">Fields Required by the ML Prediction Model</span>
            </div>
            <p className="text-xs text-emerald-100/90 max-w-3xl leading-relaxed">
              The AI Two-Stage Gradient Boosting irrigation engine calculates exact water depth based on your field's live sensor telemetry.
              Ensure probes provide:
              <span className="font-bold text-white underline decoration-emerald-400 ml-1">Soil Moisture (%)</span> (root water depletion),
              <span className="font-bold text-white underline decoration-emerald-400 ml-1">Temperature (°C)</span> (evaporative stress), and
              <span className="font-bold text-white underline decoration-emerald-400 ml-1">Relative Humidity (%)</span> (atmospheric moisture deficit).
            </p>
          </div>
          <div className="flex items-center space-x-2 shrink-0">
            <button
              onClick={() => openTelemetryModal()}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-white hover:bg-emerald-50 text-emerald-900 font-bold text-xs rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <Droplets className="w-4 h-4 text-emerald-600" />
              <span>Input Telemetry Now</span>
            </button>
          </div>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
        </div>
      )}
      {success && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-3 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col sm:flex-row items-center gap-3">
        <div className="flex-1 flex items-center space-x-2 w-full">
          <Search className="w-4 h-4 text-slate-400 ml-2" />
          <input
            type="text"
            placeholder="Search sensor ID (e.g. SM001), type, or field..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs bg-transparent border-0 focus:outline-none text-slate-800 placeholder-slate-400"
          />
        </div>
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <select
            value={fieldFilter}
            onChange={(e) => setFieldFilter(e.target.value)}
            className="text-xs p-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-700 focus:outline-none"
          >
            <option value="">All Fields</option>
            {fields.map((fld) => (
              <option key={fld.field_id} value={fld.field_id}>
                {fld.name} ({fld.field_id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Sensor ID</th>
                <th className="py-3 px-4">Field ID</th>
                <th className="py-3 px-4">Probe Type</th>
                <th className="py-3 px-4">Latest ML Telemetry</th>
                <th className="py-3 px-4">AI ML Status</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredSensors.map((s) => {
                const latest = latestReadings[s.sensor_id];
                const hasMoisture = latest?.soil_moisture !== null && latest?.soil_moisture !== undefined;
                const hasTemp = latest?.temperature !== null && latest?.temperature !== undefined;
                const hasHum = latest?.humidity !== null && latest?.humidity !== undefined;
                const isMLComplete = hasMoisture && (hasTemp || hasHum);

                return (
                  <tr key={s.sensor_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-emerald-700">
                      <div className="flex items-center space-x-1.5">
                        <span>{s.sensor_id}</span>
                        {s.is_simulated && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] bg-slate-100 text-slate-500 border border-slate-200">
                            SIM
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-600">{s.field_id}</td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900 capitalize">{s.sensor_type.replace('_', ' ')}</div>
                      <div className="text-[10px] text-slate-400">{s.unit || '—'} &bull; {s.connectivity_mode || 'cellular'}</div>
                    </td>
                    <td className="py-3 px-4">
                      {latest ? (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {hasMoisture && (
                            <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-800 text-[10px] font-semibold">
                              <Droplets className="w-3 h-3 text-blue-600" />
                              <span>{latest.soil_moisture}%</span>
                            </span>
                          )}
                          {hasTemp && (
                            <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-800 text-[10px] font-semibold">
                              <Thermometer className="w-3 h-3 text-amber-600" />
                              <span>{latest.temperature}°C</span>
                            </span>
                          )}
                          {hasHum && (
                            <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-teal-50 border border-teal-200 text-teal-800 text-[10px] font-semibold">
                              <Wind className="w-3 h-3 text-teal-600" />
                              <span>{latest.humidity}%</span>
                            </span>
                          )}
                          {latest.rainfall !== null && latest.rainfall !== undefined && latest.rainfall > 0 && (
                            <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-indigo-800 text-[10px] font-semibold">
                              <CloudRain className="w-3 h-3 text-indigo-600" />
                              <span>{latest.rainfall}mm</span>
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs italic">No readings logged yet</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {isMLComplete ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                          <Sparkles className="w-3 h-3 text-emerald-600" />
                          <span>ML Ready</span>
                        </span>
                      ) : hasMoisture ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
                          <span>Moisture Only</span>
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500">
                          Pending Inputs
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => handleToggleStatus(s)}
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-colors cursor-pointer ${
                          s.status === 'active'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                            : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'
                        }`}
                      >
                        <Power className="w-2.5 h-2.5" />
                        <span className="capitalize">{s.status}</span>
                      </button>
                    </td>
                    <td className="py-3 px-4 text-right space-x-1.5">
                      <button
                        onClick={() => openTelemetryModal(s)}
                        className="px-2 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 font-semibold rounded-lg text-[11px] transition-colors cursor-pointer inline-flex items-center space-x-1"
                        title="Log telemetry required for ML prediction"
                      >
                        <Droplets className="w-3 h-3 text-emerald-600" />
                        <span>Log Telemetry</span>
                      </button>
                      <button
                        onClick={() => handleInspectReadings(s)}
                        className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-[11px] transition-colors cursor-pointer"
                      >
                        History
                      </button>
                      <button
                        onClick={() => handleDelete(s)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                        title="Delete sensor"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
              {filteredSensors.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-slate-400">
                    {search ? 'No sensors match your query.' : 'No sensors registered yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Log ML Telemetry Modal */}
      {telemetryModalSensor && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="space-y-0.5">
                <h3 className="font-bold text-slate-900 text-sm flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-emerald-600" />
                  <span>Log Sensor Telemetry for ML Prediction</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Sensor {telemetryModalSensor.sensor_id} &bull; Field {telemetryModalSensor.field_id}
                </p>
              </div>
              <button onClick={() => setTelemetryModalSensor(null)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>

            {/* Quick Simulation Presets */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <div className="text-[11px] font-semibold text-slate-700">Quick Simulation Presets:</div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => applyPreset('optimal')}
                  className="px-2 py-1.5 bg-white hover:bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-[11px] font-medium text-center transition-colors cursor-pointer"
                >
                  🟢 Healthy (34%)
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('drought')}
                  className="px-2 py-1.5 bg-white hover:bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-[11px] font-medium text-center transition-colors cursor-pointer"
                >
                  🔴 Drought (17.5%)
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('rain')}
                  className="px-2 py-1.5 bg-white hover:bg-blue-50 border border-blue-200 rounded-lg text-blue-800 text-[11px] font-medium text-center transition-colors cursor-pointer"
                >
                  🌧️ Post-Rain (54%)
                </button>
              </div>
            </div>

            <form onSubmit={handleLogTelemetry} className="space-y-3.5">
              {/* Soil Moisture */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-800 flex items-center space-x-1">
                    <Droplets className="w-3.5 h-3.5 text-blue-600" />
                    <span>Soil Moisture (%) *</span>
                  </label>
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                    Required for ML Model
                  </span>
                </div>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  required
                  placeholder="e.g. 28.5"
                  value={telemetryData.soil_moisture}
                  onChange={(e) => setTelemetryData({ ...telemetryData, soil_moisture: e.target.value })}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600"
                />
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  Volumetric soil moisture percentage (0% = bone dry, 100% = fully waterlogged).
                </span>
              </div>

              {/* Temperature & Humidity in 2 columns */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-slate-800 flex items-center space-x-1">
                      <Thermometer className="w-3.5 h-3.5 text-amber-600" />
                      <span>Temperature (°C) *</span>
                    </label>
                  </div>
                  <input
                    type="number"
                    step="0.1"
                    min="-10"
                    max="65"
                    required
                    placeholder="e.g. 29.0"
                    value={telemetryData.temperature}
                    onChange={(e) => setTelemetryData({ ...telemetryData, temperature: e.target.value })}
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600"
                  />
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    Ambient / root-zone temp for evapotranspiration.
                  </span>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-slate-800 flex items-center space-x-1">
                      <Wind className="w-3.5 h-3.5 text-teal-600" />
                      <span>Relative Humidity (%) *</span>
                    </label>
                  </div>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    required
                    placeholder="e.g. 62.0"
                    value={telemetryData.humidity}
                    onChange={(e) => setTelemetryData({ ...telemetryData, humidity: e.target.value })}
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600"
                  />
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    Air vapor pressure deficit calculation.
                  </span>
                </div>
              </div>

              {/* Rainfall & Soil pH in 2 columns */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center space-x-1">
                    <CloudRain className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Recent Rainfall (mm)</span>
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="300"
                    placeholder="e.g. 0.0"
                    value={telemetryData.rainfall}
                    onChange={(e) => setTelemetryData({ ...telemetryData, rainfall: e.target.value })}
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600"
                  />
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    Rain recorded in last 24h.
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Soil pH (optional)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="3"
                    max="10"
                    placeholder="e.g. 6.8"
                    value={telemetryData.soil_ph}
                    onChange={(e) => setTelemetryData({ ...telemetryData, soil_ph: e.target.value })}
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600"
                  />
                  <span className="text-[10px] text-slate-400 mt-0.5 block">
                    Soil acidity/alkalinity level.
                  </span>
                </div>
              </div>

              <div className="p-2.5 rounded-xl bg-emerald-50/80 border border-emerald-200 text-[11px] text-emerald-900 flex items-start space-x-2">
                <Info className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>
                  These sensor readings feed directly into the AI Machine Learning model to calculate the exact crop water deficit and irrigation scheduling window.
                </span>
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setTelemetryModalSensor(null)}
                  className="px-4 py-2 text-xs text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs transition-colors cursor-pointer"
                >
                  {submitting ? 'Recording Telemetry...' : 'Save & Update ML Telemetry'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Register Sensor Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 className="font-bold text-slate-900 text-sm">Register IoT Sensor / Probe</h3>
              <button onClick={() => setShowAddModal(false)}>
                <X className="w-4 h-4 text-slate-400" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Assigned Field *</label>
                <select
                  required
                  value={formData.field_id}
                  onChange={(e) => setFormData({ ...formData, field_id: e.target.value })}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600 bg-white"
                >
                  {fields.map((fld) => (
                    <option key={fld.field_id} value={fld.field_id}>
                      {fld.name} ({fld.field_id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-700">Probe Capability &amp; Measurement Type *</label>
                </div>
                <select
                  value={formData.sensor_type}
                  onChange={(e) => {
                    const st = e.target.value;
                    let u = '%';
                    if (st === 'temperature') u = '°C';
                    else if (st === 'humidity') u = '%';
                    else if (st === 'multi_probe') u = 'Multi (%, °C)';
                    else if (st === 'soil_ph') u = 'pH';
                    else if (st === 'rainfall') u = 'mm';
                    else if (st === 'water_level') u = 'm';
                    else if (st === 'flow_rate') u = 'L/min';
                    setFormData({ ...formData, sensor_type: st, unit: u });
                  }}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600 bg-white"
                >
                  <option value="soil_moisture">Soil Moisture Sensor (Volumetric %) [ML Input]</option>
                  <option value="multi_probe">All-in-One Agro-Climatic Probe (Moisture + Temp + Humidity) [⭐ AI ML Recommended]</option>
                  <option value="temperature">Soil &amp; Ambient Temperature Sensor (°C) [ML Input]</option>
                  <option value="humidity">Relative Humidity Sensor (%) [ML Input]</option>
                  <option value="rainfall">Precipitation Rain Gauge (mm)</option>
                  <option value="soil_ph">Soil pH Sensor (pH)</option>
                  <option value="flow_rate">Pump Flow Meter (L/min)</option>
                </select>
              </div>

              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-[11px] space-y-1">
                <div className="font-semibold flex items-center space-x-1">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                  <span>AI ML Prediction Requirement:</span>
                </div>
                <p className="text-emerald-800/80">
                  The ML model requires <strong>Soil Moisture (%)</strong>, <strong>Temperature (°C)</strong>, and <strong>Humidity (%)</strong>. Registering an All-in-One Probe or logging all 3 parameters enables automated precision water recommendations.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Unit of Measurement</label>
                  <input
                    type="text"
                    value={formData.unit || ''}
                    onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Initial Status</label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-emerald-600 bg-white"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <label className="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_simulated}
                    onChange={(e) => setFormData({ ...formData, is_simulated: e.target.checked })}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>Mark as simulated test probe (software emulated telemetry)</span>
                </label>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-xs text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs cursor-pointer"
                >
                  {submitting ? 'Registering...' : 'Register Sensor'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Inspect Readings Modal */}
      {viewingReadings && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="font-bold text-slate-900 text-sm">
                  Telemetry Readings: {viewingReadings.sensor.sensor_id}
                </h3>
                <span className="text-xs text-slate-500">
                  Type: {viewingReadings.sensor.sensor_type} &bull; Field: {viewingReadings.sensor.field_id}
                </span>
              </div>
              <button onClick={() => setViewingReadings(null)}><X className="w-4 h-4 text-slate-400" /></button>
            </div>

            <div className="max-h-72 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                    <th className="py-2.5 px-3">Timestamp (UTC)</th>
                    <th className="py-2.5 px-3">Moisture (%)</th>
                    <th className="py-2.5 px-3">Temp (°C)</th>
                    <th className="py-2.5 px-3">Humidity (%)</th>
                    <th className="py-2.5 px-3">Rain (mm)</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {viewingReadings.readings.map((r) => (
                    <tr key={r.reading_id}>
                      <td className="py-2 px-3 font-mono text-[11px] text-slate-600">
                        {new Date(r.timestamp).toLocaleString()}
                      </td>
                      <td className="py-2 px-3 font-semibold text-emerald-700">
                        {r.soil_moisture !== null && r.soil_moisture !== undefined ? `${r.soil_moisture}%` : '—'}
                      </td>
                      <td className="py-2 px-3 text-amber-800">
                        {r.temperature !== null && r.temperature !== undefined ? `${r.temperature}°C` : '—'}
                      </td>
                      <td className="py-2 px-3 text-teal-800">
                        {r.humidity !== null && r.humidity !== undefined ? `${r.humidity}%` : '—'}
                      </td>
                      <td className="py-2 px-3 text-indigo-800">
                        {r.rainfall !== null && r.rainfall !== undefined && r.rainfall > 0 ? `${r.rainfall}mm` : '0mm'}
                      </td>
                      <td className="py-2 px-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-800">
                          {r.quality_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {viewingReadings.readings.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center py-6 text-slate-400">
                        No telemetry points recorded yet for this sensor.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-slate-100">
              <button
                onClick={() => {
                  const s = viewingReadings.sensor;
                  setViewingReadings(null);
                  openTelemetryModal(s);
                }}
                className="px-3.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 text-xs font-semibold rounded-xl flex items-center space-x-1.5 transition-colors cursor-pointer"
              >
                <Droplets className="w-3.5 h-3.5 text-emerald-600" />
                <span>Log New Telemetry Point</span>
              </button>
              <button
                onClick={() => setViewingReadings(null)}
                className="px-4 py-2 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
