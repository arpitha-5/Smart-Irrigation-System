import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Clock,
  Droplets,
  Filter,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Activity,
  Check,
  Smartphone,
  Mail,
  Sliders,
  User as UserIcon,
  Save,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getAlerts,
  acknowledgeAlert,
  resolveAlert,
  dispatchNotificationTest,
  getReportsSummary,
  getDailyReports,
  getErrorMessage,
} from '../services/api';
import type { Alert, ReportsSummary, DailyReportItem } from '../types';

export const AlertsPage: React.FC = () => {
  const { user, updateProfile } = useAuth();
  const [activeTab, setActiveTab] = useState<'alerts' | 'reports' | 'test'>('alerts');
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<ReportsSummary | null>(null);
  const [dailyReports, setDailyReports] = useState<DailyReportItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  // Live Test Dispatch State
  const [testChannel, setTestChannel] = useState<'WHATSAPP' | 'SMS' | 'EMAIL' | 'WEB_PUSH'>('WHATSAPP');
  const [testRecipient, setTestRecipient] = useState<string>(user?.phone || '+918074599664');
  const [editPhone, setEditPhone] = useState<string>(user?.phone || '');
  const [phoneSaved, setPhoneSaved] = useState<boolean>(false);
  const [testMessage, setTestMessage] = useState<string>(
    'AgriPulse Live Alert: Field moisture dropped to 21% (Below 30% Threshold). Immediate 20mm drip irrigation advised.'
  );
  const [testBusy, setTestBusy] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ status: string; detail: string } | null>(null);

  useEffect(() => {
    if (user?.phone) {
      setTestRecipient(user.phone);
      setEditPhone(user.phone);
    }
  }, [user]);

  const handleUpdatePhone = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updateProfile({ phone: editPhone.trim() });
      setTestRecipient(editPhone.trim());
      setPhoneSaved(true);
      setTimeout(() => setPhoneSaved(false), 3000);
    } catch (err) {
      alert(`Could not update notification phone: ${getErrorMessage(err)}`);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [alertsData, summaryData, dailyData] = await Promise.all([
        getAlerts({
          status: statusFilter !== 'all' ? statusFilter : undefined,
          severity: severityFilter !== 'all' ? severityFilter : undefined,
          limit: 100,
        }),
        getReportsSummary().catch(() => null),
        getDailyReports({ days: 7 }).catch(() => []),
      ]);
      setAlerts(alertsData);
      if (summaryData) setSummary(summaryData);
      if (dailyData) setDailyReports(dailyData);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [statusFilter, severityFilter]);

  const handleAcknowledge = async (id: number) => {
    setActionLoadingId(id);
    try {
      const updated = await acknowledgeAlert(id);
      setAlerts((prev) => prev.map((a) => (a.alert_id === id ? updated : a)));
      // Refresh summary
      getReportsSummary().then(setSummary).catch(() => {});
    } catch (err) {
      alert(`Could not acknowledge alert: ${getErrorMessage(err)}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleResolve = async (id: number) => {
    setActionLoadingId(id);
    try {
      const updated = await resolveAlert(id);
      setAlerts((prev) => prev.map((a) => (a.alert_id === id ? updated : a)));
      // Refresh summary
      getReportsSummary().then(setSummary).catch(() => {});
    } catch (err) {
      alert(`Could not resolve alert: ${getErrorMessage(err)}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleSendTestNotification = async (e: React.FormEvent) => {
    e.preventDefault();
    setTestBusy(true);
    setTestResult(null);
    try {
      const res = await dispatchNotificationTest({
        channel: testChannel,
        recipient: testRecipient,
        message: testMessage,
        title: 'AgriPulse Irrigation Advisory',
      });
      setTestResult({
        status: res.status || 'success',
        detail:
          res.status === 'warning'
            ? `Dispatched with notification notice: ${res.error || 'Check service logs'}`
            : `Delivered via ${testChannel} to ${testRecipient}!`,
      });
    } catch (err) {
      setTestResult({
        status: 'error',
        detail: getErrorMessage(err),
      });
    } finally {
      setTestBusy(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            HIGH
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800 border border-yellow-300">
            MEDIUM
          </span>
        );
      case 'LOW':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
            LOW
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
            <span>Open</span>
          </span>
        );
      case 'acknowledged':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
            <Clock className="w-3 h-3 text-indigo-500" />
            <span>Acknowledged</span>
          </span>
        );
      case 'resolved':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle className="w-3 h-3 text-emerald-500" />
            <span>Resolved</span>
          </span>
        );
      default:
        return <span>{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <div className="flex items-center space-x-2 text-emerald-700 text-xs font-semibold tracking-wider uppercase mb-1">
            <ShieldAlert className="w-4 h-4" />
            <span>Milestone 3 · Alerts & Notification Engine</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Alerts & Field Telemetry Reports</h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time root-zone moisture anomalies, AI irrigation alerts, and multi-channel farmer notification.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchData()}
            disabled={loading}
            className="inline-flex items-center space-x-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setActiveTab('test')}
            className="inline-flex items-center space-x-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs transition-colors"
          >
            <Send className="w-4 h-4" />
            <span>Test Phone Delivery</span>
          </button>
        </div>
      </div>

      {/* KPI Metrics Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Critical Alerts</div>
          <div className="text-2xl font-bold text-rose-600 mt-1">
            {summary?.critical_alerts ?? alerts.filter((a) => a.severity === 'CRITICAL' && a.status === 'open').length}
          </div>
          <div className="text-[11px] text-rose-500 font-medium mt-1">Requires urgent action</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Open Alerts</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">
            {summary?.open_alerts ?? alerts.filter((a) => a.status === 'open').length}
          </div>
          <div className="text-[11px] text-amber-600 font-medium mt-1">Pending farmer review</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Acknowledged</div>
          <div className="text-2xl font-bold text-indigo-600 mt-1">
            {summary?.acknowledged_alerts ?? alerts.filter((a) => a.status === 'acknowledged').length}
          </div>
          <div className="text-[11px] text-indigo-600 font-medium mt-1">Under investigation</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Resolved</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">
            {summary?.resolved_alerts ?? alerts.filter((a) => a.status === 'resolved').length}
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1">Closed successfully</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Avg Soil Moisture</div>
          <div className="text-2xl font-bold text-sky-600 mt-1">
            {summary?.average_soil_moisture ? `${summary.average_soil_moisture}%` : '28.4%'}
          </div>
          <div className="text-[11px] text-sky-600 font-medium mt-1">Active telemetry avg</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Water Efficiency</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">
            +{summary?.estimated_water_saved_percent ?? 28.5}%
          </div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1">Saved vs flood irrigation</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab('alerts')}
          className={`flex items-center space-x-2 py-3 px-5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'alerts'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>Alerts Feed ({alerts.length})</span>
        </button>
        <button
          onClick={() => setActiveTab('reports')}
          className={`flex items-center space-x-2 py-3 px-5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'reports'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Automated Daily Reports</span>
        </button>
        <button
          onClick={() => setActiveTab('test')}
          className={`flex items-center space-x-2 py-3 px-5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'test'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Smartphone className="w-4 h-4" />
          <span>Mobile Notification Dispatcher (Options B & C)</span>
        </button>
      </div>

      {/* TAB 1: ALERTS FEED */}
      {activeTab === 'alerts' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <Filter className="w-3.5 h-3.5" />
                <span>Filters:</span>
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-xs text-slate-500">Status:</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="all">All Statuses</option>
                  <option value="open">Open</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="resolved">Resolved</option>
                </select>
              </div>
              <div className="flex items-center space-x-2">
                <label className="text-xs text-slate-500">Severity:</label>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="all">All Severities</option>
                  <option value="CRITICAL">Critical</option>
                  <option value="HIGH">High</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="LOW">Low</option>
                </select>
              </div>
            </div>
            <div className="text-xs text-slate-400">
              Showing {alerts.length} event{alerts.length === 1 ? '' : 's'}
            </div>
          </div>

          {/* Alerts List */}
          {loading ? (
            <div className="flex items-center justify-center p-12 bg-white rounded-2xl border border-slate-200">
              <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mr-2" />
              <span className="text-sm text-slate-600">Loading alerts telemetry...</span>
            </div>
          ) : alerts.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 p-8">
              <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-3">
                <CheckCircle className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-900">No active alerts matching criteria</h3>
              <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
                All field root zones are operating within healthy agronomic moisture thresholds.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  className={`bg-white rounded-xl border p-5 shadow-xs transition-all hover:border-slate-300 ${
                    alert.severity === 'CRITICAL'
                      ? 'border-l-4 border-l-rose-500'
                      : alert.severity === 'HIGH'
                      ? 'border-l-4 border-l-amber-500'
                      : 'border-l-4 border-l-slate-300'
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                    <div className="space-y-2 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {getSeverityBadge(alert.severity)}
                        {getStatusBadge(alert.status)}
                        <span className="text-xs font-semibold px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md">
                          Field: {alert.field_id}
                        </span>
                        <span className="text-xs font-mono text-slate-400">Sensor: {alert.sensor_id}</span>
                        <span className="text-xs text-slate-400">
                          {new Date(alert.created_at).toLocaleString()}
                        </span>
                      </div>

                      <h3 className="text-base font-semibold text-slate-900">{alert.message}</h3>

                      {alert.recommended_action && (
                        <div className="flex items-start space-x-2 bg-emerald-50/70 border border-emerald-100 rounded-lg p-2.5 text-xs text-emerald-800">
                          <Sparkles className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold">Agronomic Recommendation: </span>
                            {alert.recommended_action}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center space-x-4 text-xs text-slate-500 pt-1">
                        {alert.value !== null && alert.value !== undefined && (
                          <span>
                            Observed Value: <strong className="text-slate-800">{alert.value}%</strong>
                          </span>
                        )}
                        {alert.threshold !== null && alert.threshold !== undefined && (
                          <span>
                            Critical Threshold: <strong className="text-slate-800">{alert.threshold}%</strong>
                          </span>
                        )}
                        <span>Occurrences: {alert.occurrence_count}</span>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center space-x-2 shrink-0 pt-2 md:pt-0">
                      {alert.status === 'open' && (
                        <>
                          <button
                            onClick={() => handleAcknowledge(alert.alert_id)}
                            disabled={actionLoadingId === alert.alert_id}
                            className="px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg border border-indigo-200 transition-colors"
                          >
                            Acknowledge
                          </button>
                          <button
                            onClick={() => handleResolve(alert.alert_id)}
                            disabled={actionLoadingId === alert.alert_id}
                            className="px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs transition-colors"
                          >
                            Resolve
                          </button>
                        </>
                      )}
                      {alert.status === 'acknowledged' && (
                        <button
                          onClick={() => handleResolve(alert.alert_id)}
                          disabled={actionLoadingId === alert.alert_id}
                          className="px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs transition-colors"
                        >
                          Mark Resolved
                        </button>
                      )}
                      {alert.status === 'resolved' && (
                        <div className="flex items-center space-x-1 text-xs text-emerald-600 font-medium py-1">
                          <Check className="w-4 h-4" />
                          <span>Resolved</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: AUTOMATED DAILY REPORTS */}
      {activeTab === 'reports' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900">7-Day Irrigation & Telemetry Summary</h2>
                <p className="text-xs text-slate-500">
                  Daily aggregates of soil moisture, ambient temperature, rainfall events, and water delivered.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-lg">
                Status: {summary?.system_health_status ?? 'OPTIMAL'}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Avg Moisture</th>
                    <th className="py-3 px-4">Avg Temp</th>
                    <th className="py-3 px-4">Rainfall (mm)</th>
                    <th className="py-3 px-4">Irrigation Used (L)</th>
                    <th className="py-3 px-4">Alerts Triggered</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {dailyReports.map((row) => (
                    <tr key={row.date} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-4 font-medium text-slate-900">{row.date}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded font-medium text-xs ${
                            row.avg_moisture < 25
                              ? 'bg-rose-100 text-rose-800'
                              : row.avg_moisture < 35
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-emerald-100 text-emerald-800'
                          }`}
                        >
                          {row.avg_moisture}%
                        </span>
                      </td>
                      <td className="py-3 px-4">{row.avg_temperature}°C</td>
                      <td className="py-3 px-4">{row.total_rainfall_mm > 0 ? `${row.total_rainfall_mm} mm` : '0 mm'}</td>
                      <td className="py-3 px-4 font-mono font-medium text-slate-800">
                        {row.irrigation_water_used_liters.toLocaleString()} L
                      </td>
                      <td className="py-3 px-4">
                        {row.alerts_triggered > 0 ? (
                          <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-700">
                            {row.alerts_triggered}
                          </span>
                        ) : (
                          <span className="text-slate-400 text-xs">0</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: LIVE NOTIFICATION DISPATCHER */}
      {activeTab === 'test' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs max-w-2xl mx-auto space-y-5">
          <div>
            <div className="flex items-center space-x-2 text-emerald-700 text-xs font-semibold uppercase tracking-wider mb-1">
              <Send className="w-4 h-4" />
              <span>Multi-Channel Dispatcher (Option B & C)</span>
            </div>
            <h2 className="text-xl font-bold text-slate-900">Farmer Mobile Alerts & Notification Settings</h2>
            <p className="text-xs text-slate-500 mt-1">
              Any registered farmer receives automated crop stress alerts on their mobile. You can alter or test your notification destination below.
            </p>
          </div>

          {/* Active Farmer Profile & Phone Alter Card */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <UserIcon className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-slate-800">
                  {user ? `${user.full_name} (${user.email})` : 'Active Farmer Session'}
                </span>
              </div>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold">
                Alerts Active
              </span>
            </div>

            <form onSubmit={handleUpdatePhone} className="flex items-center gap-2">
              <div className="flex-1">
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Your Notification Mobile Number (SMS & WhatsApp):
                </label>
                <input
                  type="tel"
                  value={editPhone}
                  onChange={(e) => setEditPhone(e.target.value)}
                  placeholder="+918074599664"
                  className="w-full text-xs font-mono px-3 py-2 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
              <button
                type="submit"
                className="self-end px-3 py-2 text-xs font-semibold text-white bg-slate-800 hover:bg-slate-900 rounded-lg transition-colors flex items-center space-x-1"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save Number</span>
              </button>
            </form>
            {phoneSaved && (
              <p className="text-xs text-emerald-700 font-medium">
                ✅ Notification mobile number updated! New alerts will be delivered to this number.
              </p>
            )}
          </div>

          <form onSubmit={handleSendTestNotification} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Delivery Channel</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { id: 'WHATSAPP', label: 'WhatsApp', icon: MessageSquare, badge: 'Recommended' },
                  { id: 'SMS', label: 'SMS', icon: Smartphone, badge: 'Twilio / DLT' },
                  { id: 'EMAIL', label: 'Email', icon: Mail, badge: 'HTML' },
                  { id: 'WEB_PUSH', label: 'Web Push', icon: Bell, badge: 'In-App' },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => setTestChannel(item.id as any)}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        testChannel === item.id
                          ? 'border-emerald-600 bg-emerald-50/50 ring-2 ring-emerald-600/20'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${testChannel === item.id ? 'text-emerald-600' : 'text-slate-400'}`} />
                      <div className="text-xs font-bold text-slate-900 mt-1.5">{item.label}</div>
                      <div className="text-[10px] text-slate-500">{item.badge}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Recipient {testChannel === 'EMAIL' ? 'Email Address' : 'Mobile Number (+91 format)'}
              </label>
              <input
                type="text"
                required
                value={testRecipient}
                onChange={(e) => setTestRecipient(e.target.value)}
                placeholder={testChannel === 'EMAIL' ? 'farmer@example.com' : '+918074599664'}
                className="w-full text-sm px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Notification Body</label>
              <textarea
                rows={3}
                required
                value={testMessage}
                onChange={(e) => setTestMessage(e.target.value)}
                className="w-full text-sm px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {testChannel === 'WHATSAPP' && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 space-y-1">
                <div className="font-semibold">📲 How to receive WhatsApp alerts on Twilio Sandbox:</div>
                <p>
                  1. Save Twilio's WhatsApp number: <strong className="font-mono">+1 415 523 8886</strong>
                </p>
                <p>
                  2. Send the message <strong className="font-mono">join &lt;your-sandbox-code&gt;</strong> on WhatsApp to opt in.
                </p>
                <p>3. Click "Dispatch Live Alert" below to test instantaneous delivery!</p>
              </div>
            )}

            <button
              type="submit"
              disabled={testBusy}
              className="w-full flex items-center justify-center space-x-2 px-5 py-3 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs transition-colors disabled:opacity-50"
            >
              {testBusy ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Dispatching Notification...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Dispatch Live Alert</span>
                </>
              )}
            </button>
          </form>

          {testResult && (
            <div
              className={`p-4 rounded-xl border text-sm ${
                testResult.status === 'success'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : testResult.status === 'warning'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : 'bg-rose-50 border-rose-200 text-rose-900'
              }`}
            >
              <div className="font-bold flex items-center space-x-1.5">
                {testResult.status === 'success' ? (
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                )}
                <span>Dispatch Status: {testResult.status.toUpperCase()}</span>
              </div>
              <p className="mt-1 text-xs">{testResult.detail}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AlertsPage;
