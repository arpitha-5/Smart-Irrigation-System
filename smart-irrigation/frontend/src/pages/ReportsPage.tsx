import React, { useEffect, useState } from 'react';
import {
  FileText,
  Download,
  Calendar,
  Languages,
  Droplets,
  Clock,
  CheckCircle2,
  AlertCircle,
  Activity,
  CloudRain,
  Settings,
  PlusCircle,
  FileSpreadsheet,
} from 'lucide-react';
import {
  getFields,
  getReportSummary,
  downloadPdfReport,
  downloadCsvReport,
  updateField,
  getIrrigationLogs,
  createIrrigationLog,
  getErrorMessage,
} from '../services/api';
import type { Field, ReportSummary, IrrigationLog } from '../types';
import { useLanguage } from '../context/LanguageContext';

export const ReportsPage: React.FC = () => {
  const { t, language } = useLanguage();

  const [fields, setFields] = useState<Field[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string>('');
  const [selectedLang, setSelectedLang] = useState<string>(language || 'en');
  const [dateFilterMode, setDateFilterMode] = useState<'all' | '7d' | '30d' | 'custom'>('30d');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [irrigationLogs, setIrrigationLogs] = useState<IrrigationLog[]>([]);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Flow rate configuration state for selected field
  const [flowRateInput, setFlowRateInput] = useState<string>('');
  const [methodInput, setMethodInput] = useState<string>('Drip');
  const [savingFlowRate, setSavingFlowRate] = useState(false);

  // New irrigation event logging modal/inline state
  const [showLogModal, setShowLogModal] = useState(false);
  const [logDepthMm, setLogDepthMm] = useState<number>(20);
  const [logDurationMin, setLogDurationMin] = useState<number>(60);
  const [logNotes, setLogNotes] = useState<string>('');
  const [loggingEvent, setLoggingEvent] = useState(false);

  // Sync selectedLang with app language if user hasn't explicitly overridden
  useEffect(() => {
    if (language) {
      setSelectedLang(language);
    }
  }, [language]);

  // Load fields on mount
  useEffect(() => {
    const loadFields = async () => {
      try {
        const flds = await getFields();
        setFields(flds);
        if (flds.length > 0) {
          setSelectedFieldId(flds[0].field_id);
          setFlowRateInput(flds[0].pump_flow_rate_lpm ? String(flds[0].pump_flow_rate_lpm) : '');
          setMethodInput(flds[0].irrigation_method || 'Drip');
        }
      } catch (err) {
        setError(getErrorMessage(err));
      }
    };
    loadFields();
  }, []);

  // Compute ISO dates based on filter mode
  const getDateRange = () => {
    const now = new Date();
    if (dateFilterMode === '7d') {
      const start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      return { startDate: start.toISOString(), endDate: now.toISOString() };
    }
    if (dateFilterMode === '30d') {
      const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      return { startDate: start.toISOString(), endDate: now.toISOString() };
    }
    if (dateFilterMode === 'custom' && startDate && endDate) {
      return {
        startDate: new Date(startDate).toISOString(),
        endDate: new Date(endDate).toISOString(),
      };
    }
    return { startDate: undefined, endDate: undefined };
  };

  // Fetch report summary and historical logs whenever field, dates, or lang change
  const refreshSummary = async () => {
    if (!selectedFieldId) return;
    setLoadingSummary(true);
    setError(null);
    try {
      const { startDate: s, endDate: e } = getDateRange();
      const [sum, logs] = await Promise.all([
        getReportSummary(selectedFieldId, { startDate: s, endDate: e, lang: selectedLang }),
        getIrrigationLogs(selectedFieldId),
      ]);
      setSummary(sum);
      setIrrigationLogs(logs);

      // Keep flow rate form synced with active field
      const currentField = fields.find((f) => f.field_id === selectedFieldId);
      if (currentField) {
        setFlowRateInput(currentField.pump_flow_rate_lpm ? String(currentField.pump_flow_rate_lpm) : '');
        setMethodInput(currentField.irrigation_method || 'Drip');
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoadingSummary(false);
    }
  };

  useEffect(() => {
    refreshSummary();
  }, [selectedFieldId, dateFilterMode, startDate, endDate, selectedLang]);

  // Handle flow rate update on field
  const handleSaveFlowRate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFieldId) return;
    setSavingFlowRate(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const rateVal = flowRateInput.trim() ? parseFloat(flowRateInput) : undefined;
      await updateField(selectedFieldId, {
        pump_flow_rate_lpm: rateVal,
        irrigation_method: methodInput,
      });

      // Update local fields state
      setFields((prev) =>
        prev.map((f) =>
          f.field_id === selectedFieldId
            ? { ...f, pump_flow_rate_lpm: rateVal ?? null, irrigation_method: methodInput }
            : f
        )
      );

      setSuccessMsg('Pump flow rate updated successfully. Durations recalculated.');
      await refreshSummary();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSavingFlowRate(false);
    }
  };

  // Handle PDF Download
  const handleDownloadPdf = async () => {
    if (!selectedFieldId) return;
    setDownloadingPdf(true);
    setError(null);
    try {
      const { startDate: s, endDate: e } = getDateRange();
      await downloadPdfReport(selectedFieldId, {
        startDate: s,
        endDate: e,
        lang: selectedLang,
      });
      setSuccessMsg(`PDF report generated and downloaded successfully in ${selectedLang.toUpperCase()}.`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDownloadingPdf(false);
    }
  };

  // Handle CSV Download
  const handleDownloadCsv = async () => {
    if (!selectedFieldId) return;
    setDownloadingCsv(true);
    setError(null);
    try {
      const { startDate: s, endDate: e } = getDateRange();
      await downloadCsvReport(selectedFieldId, {
        startDate: s,
        endDate: e,
      });
      setSuccessMsg('Excel/CSV report generated and downloaded with UTF-8 BOM encoding.');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDownloadingCsv(false);
    }
  };

  // Handle manual irrigation event creation
  const handleCreateIrrigationLog = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFieldId) return;
    setLoggingEvent(true);
    setError(null);
    try {
      const currentField = fields.find((f) => f.field_id === selectedFieldId);
      const flowRate = currentField?.pump_flow_rate_lpm || (flowRateInput ? parseFloat(flowRateInput) : undefined);

      await createIrrigationLog({
        field_id: selectedFieldId,
        water_depth_mm: logDepthMm,
        duration_minutes: logDurationMin,
        flow_rate_lpm: flowRate,
        source: 'manual',
        notes: logNotes || 'Manual irrigation cycle completed by farmer',
      });

      setShowLogModal(false);
      setLogNotes('');
      setSuccessMsg('Actual irrigation event logged to database.');
      await refreshSummary();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoggingEvent(false);
    }
  };

  const selectedField = fields.find((f) => f.field_id === selectedFieldId);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <FileText className="w-6 h-6 text-emerald-600" />
            <h1 className="text-xl font-bold text-slate-900">
              {t('reports.title', 'Field Irrigation & Telemetry Reports')}
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {t(
              'reports.subtitle',
              'Generate downloadable multilingual PDF & Excel/CSV reports for crop audits, moisture records, and irrigation schedules.'
            )}
          </p>
        </div>

        <button
          onClick={() => setShowLogModal(true)}
          className="inline-flex items-center space-x-2 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer"
        >
          <PlusCircle className="w-4 h-4" />
          <span>{t('reports.logIrrigationEvent', 'Log Irrigation Event')}</span>
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Control Card: Field, Language & Date Filters */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Field Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              {t('reports.selectField', 'Select Field')}
            </label>
            <select
              value={selectedFieldId}
              onChange={(e) => setSelectedFieldId(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
            >
              {fields.map((f) => (
                <option key={f.field_id} value={f.field_id}>
                  {f.name} ({f.field_id}) — {f.crop_type} ({f.area_hectares || 1.0} ha)
                </option>
              ))}
            </select>
            {selectedField && (
              <div className="mt-1 flex items-center space-x-2 text-[11px] text-slate-500">
                <span>Method: <b>{selectedField.irrigation_method || 'Drip'}</b></span>
                <span>&bull;</span>
                <span>
                  Flow: <b>{selectedField.pump_flow_rate_lpm ? `${selectedField.pump_flow_rate_lpm} LPM` : 'Not set'}</b>
                </span>
              </div>
            )}
          </div>

          {/* Language Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center space-x-1.5">
              <Languages className="w-3.5 h-3.5 text-emerald-600" />
              <span>{t('reports.language', 'Report Language')}</span>
            </label>
            <select
              value={selectedLang}
              onChange={(e) => setSelectedLang(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
            >
              <option value="en">English (English)</option>
              <option value="te">తెలుగు (Telugu)</option>
              <option value="hi">हिन्दी (Hindi)</option>
              <option value="ta">தமிழ் (Tamil)</option>
              <option value="kn">ಕನ್ನಡ (Kannada)</option>
            </select>
            <p className="mt-1 text-[10px] text-slate-400">
              PDF reports will be rendered natively in your chosen regional language.
            </p>
          </div>

          {/* Date Filter Range */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center space-x-1.5">
              <Calendar className="w-3.5 h-3.5 text-emerald-600" />
              <span>{t('reports.dateRange', 'Date Range Filter')}</span>
            </label>
            <div className="grid grid-cols-4 gap-1">
              {(['7d', '30d', 'all', 'custom'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setDateFilterMode(mode)}
                  className={`py-1.5 px-2 rounded-lg text-[11px] font-semibold transition-all cursor-pointer ${
                    dateFilterMode === mode
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {mode === '7d' ? '7 Days' : mode === '30d' ? '30 Days' : mode === 'all' ? 'All' : 'Custom'}
                </button>
              ))}
            </div>

            {dateFilterMode === 'custom' && (
              <div className="grid grid-cols-2 gap-2 mt-2">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="px-2 py-1 text-[11px] rounded-lg border border-slate-200"
                />
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="px-2 py-1 text-[11px] rounded-lg border border-slate-200"
                />
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
          <div className="text-xs text-slate-500">
            {loadingSummary ? 'Compiling telemetry and logs...' : 'Ready to download official field report.'}
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleDownloadCsv}
              disabled={downloadingCsv || !selectedFieldId}
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold rounded-xl transition-colors shadow-xs cursor-pointer disabled:opacity-50"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
              <span>{downloadingCsv ? 'Generating CSV...' : t('reports.downloadCsv', 'Download CSV (Excel)')}</span>
            </button>

            <button
              onClick={handleDownloadPdf}
              disabled={downloadingPdf || !selectedFieldId}
              className="inline-flex items-center space-x-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl transition-colors shadow-xs cursor-pointer disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              <span>{downloadingPdf ? 'Building PDF...' : t('reports.downloadPdf', 'Download PDF Report')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Summary Card + Flow Rate Config */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Report Telemetry & Scheduling Audit */}
        <div className="lg:col-span-2 space-y-5">
          {summary ? (
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-5">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center space-x-2">
                  <Activity className="w-5 h-5 text-emerald-600" />
                  <h3 className="text-sm font-bold text-slate-900">
                    {t('reports.reportSummary', 'Report Summary & Telemetry Audit')}
                  </h3>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                  {summary.field_id}
                </span>
              </div>

              {/* Profiles Header */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Farmer</div>
                  <div className="font-bold text-slate-900 mt-0.5">{summary.farmer_name}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Field / Crop</div>
                  <div className="font-bold text-slate-900 mt-0.5 capitalize">
                    {summary.field_name} &bull; {summary.crop_name}
                  </div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Area</div>
                  <div className="font-bold text-slate-900 mt-0.5">{summary.area_hectares || '1.0'} ha</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Method</div>
                  <div className="font-bold text-slate-900 mt-0.5">{summary.irrigation_method || 'Drip'}</div>
                </div>
              </div>

              {/* Scheduling & ML Water Requirement Highlight */}
              <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/50 space-y-3">
                <div className="text-xs font-bold text-emerald-950 uppercase tracking-wide flex items-center space-x-1.5">
                  <Droplets className="w-4 h-4 text-emerald-600" />
                  <span>AI ML Water Prediction & Irrigation Schedule</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 bg-white rounded-xl border border-emerald-100">
                    <div className="text-[10px] text-slate-400">ML Water Requirement</div>
                    <div className="text-lg font-black text-slate-900">
                      {summary.ml_water_requirement_mm !== null ? `${summary.ml_water_requirement_mm} mm` : '0 mm'}
                    </div>
                    <div className="text-[11px] text-emerald-700 font-semibold">
                      {summary.water_volume_litres !== null
                        ? `${summary.water_volume_litres.toLocaleString()} Litres`
                        : 'N/A'}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-xl border border-emerald-100">
                    <div className="text-[10px] text-slate-400">Recommended Time Window</div>
                    <div className="text-sm font-bold text-slate-900">
                      {summary.recommended_date || 'Today'}
                    </div>
                    <div className="text-xs font-bold text-blue-700 mt-0.5">
                      {summary.recommended_time_window || 'Immediate'}
                    </div>
                  </div>

                  <div className="p-3 bg-white rounded-xl border border-emerald-100">
                    <div className="text-[10px] text-slate-400">Estimated Duration</div>
                    <div className="text-lg font-black text-slate-900">
                      {summary.estimated_duration_minutes !== null
                        ? `${summary.estimated_duration_minutes} min`
                        : 'Flow rate not configured'}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Flow: {summary.pump_flow_rate_lpm ? `${summary.pump_flow_rate_lpm} LPM` : 'Not set'}
                    </div>
                  </div>
                </div>

                {summary.scheduling_reason && (
                  <p className="text-xs text-slate-700 leading-relaxed bg-white/70 p-2.5 rounded-lg border border-emerald-100">
                    <b>Advisory Reasoning:</b> {summary.scheduling_reason}
                  </p>
                )}
              </div>

              {/* Telemetry Counts Audit */}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-xl font-bold text-slate-900">{summary.sensor_readings_count}</div>
                  <div className="text-[10px] text-slate-500 uppercase mt-0.5 font-medium">Sensor Readings</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-xl font-bold text-slate-900">{summary.weather_records_count}</div>
                  <div className="text-[10px] text-slate-500 uppercase mt-0.5 font-medium">Weather Logs</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-xl font-bold text-slate-900">{summary.irrigation_records_count}</div>
                  <div className="text-[10px] text-slate-500 uppercase mt-0.5 font-medium">Irrigation Events</div>
                </div>
              </div>

              {/* Historical Irrigation Records Table */}
              <div>
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Actual Irrigation Logs (Stored in Database)
                </h4>
                {irrigationLogs.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-2 px-3">Timestamp (UTC)</th>
                          <th className="py-2 px-3">Depth (mm)</th>
                          <th className="py-2 px-3">Volume (L)</th>
                          <th className="py-2 px-3">Duration (min)</th>
                          <th className="py-2 px-3">Flow (LPM)</th>
                          <th className="py-2 px-3">Source</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {irrigationLogs.slice(0, 5).map((log) => (
                          <tr key={log.log_id} className="hover:bg-slate-50">
                            <td className="py-2 px-3 font-mono text-[11px] text-slate-600">
                              {log.timestamp.slice(0, 16).replace('T', ' ')}
                            </td>
                            <td className="py-2 px-3 font-bold text-slate-800">{log.water_depth_mm} mm</td>
                            <td className="py-2 px-3 text-slate-700">
                              {log.water_volume_litres ? log.water_volume_litres.toLocaleString() : 'N/A'}
                            </td>
                            <td className="py-2 px-3 text-slate-600">{log.duration_minutes ?? 'N/A'}</td>
                            <td className="py-2 px-3 text-slate-600">{log.flow_rate_lpm ?? 'N/A'}</td>
                            <td className="py-2 px-3">
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 uppercase">
                                {log.source}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic p-3 bg-slate-50 rounded-xl">
                    No actual irrigation events logged yet for this field. Use &quot;Log Irrigation Event&quot; above to record
                    field operations.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white p-10 rounded-2xl border border-slate-200/80 shadow-xs text-center text-slate-400">
              {loadingSummary ? 'Compiling telemetry audit...' : 'Select a field to preview report contents.'}
            </div>
          )}
        </div>

        {/* Right Col: Flow Rate Configuration */}
        <div className="space-y-5">
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
            <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
              <Settings className="w-4 h-4 text-emerald-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                {t('reports.flowRateConfig', 'Pump Flow Rate Configuration')}
              </h3>
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              {t(
                'reports.flowRateHelp',
                "Configure your irrigation system's pump flow rate in Litres Per Minute (LPM). This enables accurate irrigation duration calculations from ML predicted water volume."
              )}
            </p>

            <form onSubmit={handleSaveFlowRate} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Pump Flow Rate (Litres / Minute)
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="any"
                    min="1"
                    placeholder="e.g. 250"
                    value={flowRateInput}
                    onChange={(e) => setFlowRateInput(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-bold text-slate-800"
                  />
                  <span className="absolute right-3 top-2 text-xs text-slate-400 font-semibold">LPM</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Irrigation Delivery Method
                </label>
                <select
                  value={methodInput}
                  onChange={(e) => setMethodInput(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                >
                  <option value="Drip">Drip Irrigation (High efficiency)</option>
                  <option value="Sprinkler">Sprinkler System</option>
                  <option value="Flood">Surface / Flood Irrigation</option>
                  <option value="Micro-sprinkler">Micro-sprinkler</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={savingFlowRate}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer"
              >
                {savingFlowRate ? 'Saving...' : t('reports.saveFlowRate', 'Save Flow Rate')}
              </button>
            </form>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-[11px] text-slate-600 space-y-1">
              <div className="font-semibold text-slate-800">Calculation Formula:</div>
              <div className="font-mono text-[10px] text-emerald-800">
                Water Volume (L) = ML Depth (mm) &times; Area (ha) &times; 10,000
              </div>
              <div className="font-mono text-[10px] text-emerald-800">
                Duration (min) = Water Volume (L) / Flow Rate (LPM)
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Manual Irrigation Event Modal */}
      {showLogModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <Clock className="w-5 h-5 text-emerald-600" />
                <h3 className="text-sm font-bold text-slate-900">Record Actual Irrigation Event</h3>
              </div>
              <button
                onClick={() => setShowLogModal(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateIrrigationLog} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Water Depth Applied (mm)
                </label>
                <input
                  type="number"
                  step="any"
                  min="0.1"
                  value={logDepthMm}
                  onChange={(e) => setLogDepthMm(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Irrigation Duration (Minutes)
                </label>
                <input
                  type="number"
                  step="any"
                  min="1"
                  value={logDurationMin}
                  onChange={(e) => setLogDurationMin(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Operational Notes (Optional)
                </label>
                <textarea
                  value={logNotes}
                  onChange={(e) => setLogNotes(e.target.value)}
                  rows={2}
                  placeholder="e.g. Morning valve cycle #2 completed"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowLogModal(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loggingEvent}
                  className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-semibold"
                >
                  {loggingEvent ? 'Saving...' : 'Save Irrigation Record'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
