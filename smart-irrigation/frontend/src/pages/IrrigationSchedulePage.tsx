import React, { useEffect, useState, useMemo } from 'react';
import {
  CalendarClock,
  CheckCircle2,
  XCircle,
  Clock,
  Plus,
  RefreshCw,
  Droplets,
  AlertTriangle,
  Sparkles,
  Filter,
  Check,
  Calendar,
  Edit2,
  Trash2,
  Download,
  CloudRain,
  Ban,
  X,
  Layers,
  ArrowRight,
} from 'lucide-react';
import {
  getIrrigationSchedules,
  generateIrrigationSchedule,
  updateIrrigationScheduleStatus,
  updateIrrigationSchedule,
  deleteIrrigationSchedule,
  createIrrigationSchedule,
  exportSchedulesToCsv,
  getFields,
  getErrorMessage,
} from '../services/api';
import type { IrrigationSchedule, Field } from '../types';
import { useLanguage } from '../context/LanguageContext';
import './IrrigationSchedulePage.css';

export const IrrigationSchedulePage: React.FC = () => {
  const { t } = useLanguage();
  const [schedules, setSchedules] = useState<IrrigationSchedule[]>([]);
  const [fields, setFields] = useState<Field[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filter states
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'completed' | 'skipped' | 'cancelled'>('all');
  const [selectedFieldId, setSelectedFieldId] = useState<string>('all');
  const [showOnlyToday, setShowOnlyToday] = useState<boolean>(false);
  const [startDateFilter, setStartDateFilter] = useState<string>('');
  const [endDateFilter, setEndDateFilter] = useState<string>('');

  // Manual modal state
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newSchedule, setNewSchedule] = useState({
    field_id: '',
    recommended_date: new Date().toISOString().split('T')[0],
    recommended_time: '06:00',
    duration_minutes: 30,
    water_quantity_liters: 1200,
    priority: 'normal',
    reason: 'Routine scheduled irrigation',
  });

  // Edit modal state
  const [editingSchedule, setEditingSchedule] = useState<IrrigationSchedule | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [fieldList, schedList] = await Promise.all([
        getFields(),
        getIrrigationSchedules({ limit: 500 }),
      ]);
      setFields(fieldList);
      const fieldIds = new Set(fieldList.map((field) => field.field_id).filter(Boolean) as string[]);
      setSchedules(schedList.filter((schedule) => schedule.field_id && fieldIds.has(schedule.field_id)));
      if (fieldList.length > 0 && !newSchedule.field_id) {
        setNewSchedule((prev) => ({ ...prev, field_id: fieldList[0].field_id }));
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

  const handleStatusChange = async (scheduleId: string, newStatus: 'pending' | 'completed' | 'skipped' | 'cancelled') => {
    try {
      setError(null);
      const updated = await updateIrrigationScheduleStatus(scheduleId, newStatus);
      setSchedules((prev) =>
        prev.map((s) => (s.schedule_id === scheduleId ? updated : s))
      );
      setSuccessMsg(`Schedule status marked as ${newStatus}.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleUpdateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSchedule) return;
    try {
      setLoading(true);
      setError(null);
      const updated = await updateIrrigationSchedule(editingSchedule.schedule_id, {
        recommended_date: editingSchedule.recommended_date || undefined,
        recommended_time: editingSchedule.recommended_time || undefined,
        duration_minutes: Number(editingSchedule.duration_minutes),
        water_quantity_liters: Number(editingSchedule.water_quantity_liters),
        priority: editingSchedule.priority || undefined,
        reason: editingSchedule.reason || undefined,
      });
      setSchedules((prev) =>
        prev.map((s) => (s.schedule_id === editingSchedule.schedule_id ? updated : s))
      );
      setEditingSchedule(null);
      setSuccessMsg('Irrigation schedule updated successfully.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!window.confirm(`Are you sure you want to delete schedule ${scheduleId}?`)) return;
    try {
      setError(null);
      await deleteIrrigationSchedule(scheduleId);
      setSchedules((prev) => prev.filter((s) => s.schedule_id !== scheduleId));
      setSuccessMsg(`Schedule ${scheduleId} deleted.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleGenerateSchedule = async (fieldId: string) => {
    try {
      setGenerating(true);
      setError(null);
      const gen = await generateIrrigationSchedule(fieldId);
      setSchedules((prev) => [gen, ...prev.filter((s) => s.schedule_id !== gen.schedule_id)]);
      const targetFieldName = fields.find((f) => f.field_id === fieldId)?.name || fieldId;
      setSuccessMsg(`Generated AI/FAO-56 Irrigation Schedule for "${targetFieldName}"!`);
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleCreateManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSchedule.field_id) {
      setError('Please select a target field');
      return;
    }
    try {
      setLoading(true);
      const created = await createIrrigationSchedule({
        field_id: newSchedule.field_id,
        recommended_date: newSchedule.recommended_date,
        recommended_time: newSchedule.recommended_time,
        duration_minutes: Number(newSchedule.duration_minutes),
        water_quantity_liters: Number(newSchedule.water_quantity_liters),
        priority: newSchedule.priority,
        reason: newSchedule.reason,
      });
      setSchedules((prev) => [created, ...prev]);
      setShowAddModal(false);
      setSuccessMsg('Irrigation event scheduled successfully.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const todayStr = useMemo(() => new Date().toISOString().split('T')[0], []);

  const filteredSchedules = useMemo(() => {
    return schedules.filter((s) => {
      if (statusFilter !== 'all' && s.status !== statusFilter) return false;
      if (selectedFieldId !== 'all' && s.field_id !== selectedFieldId) return false;
      const itemDate = (s.recommended_date || '').split('T')[0];
      if (showOnlyToday && itemDate !== todayStr) return false;
      if (startDateFilter && itemDate < startDateFilter) return false;
      if (endDateFilter && itemDate > endDateFilter) return false;
      return true;
    });
  }, [schedules, statusFilter, selectedFieldId, showOnlyToday, todayStr, startDateFilter, endDateFilter]);

  // Aggregate metrics
  const todaySchedules = schedules.filter((s) => (s.recommended_date || '').split('T')[0] === todayStr);
  const pendingCount = schedules.filter((s) => s.status === 'pending').length;
  const completedCount = schedules.filter((s) => s.status === 'completed').length;
  const totalWaterPending = schedules
    .filter((s) => s.status === 'pending')
    .reduce((acc, curr) => acc + (curr.water_quantity_liters || 0), 0);

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2.5 rounded-2xl bg-emerald-100 text-emerald-800 border border-emerald-200 shadow-2xs">
              <CalendarClock className="w-6 h-6" />
            </span>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {t('nav.schedules', 'Irrigation Schedules')}
              </h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Automated FAO-56 crop water scheduling, field event tracking, and pump actuation management.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
            <span>{t('common.refresh', 'Refresh')}</span>
          </button>

          {filteredSchedules.length > 0 && (
            <button
              type="button"
              onClick={() => exportSchedulesToCsv(filteredSchedules)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold shadow-2xs transition-all active:scale-95"
              title="Export filtered schedules to CSV"
            >
              <Download className="w-3.5 h-3.5 text-emerald-600" />
              <span>Export CSV</span>
            </button>
          )}

          {fields.length > 0 && (
            <button
              type="button"
              onClick={() => handleGenerateSchedule(selectedFieldId !== 'all' ? selectedFieldId : fields[0].field_id)}
              disabled={generating}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-semibold shadow-xs transition-all active:scale-95 disabled:opacity-50"
            >
              <Sparkles className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
              <span>{generating ? 'Analyzing Soil & FAO-56...' : 'AI Auto-Schedule'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-all active:scale-95"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Schedule</span>
          </button>
        </div>
      </div>

      {/* Alert Notifications */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center justify-between text-xs shadow-2xs">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-medium">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="p-1 hover:bg-rose-100 rounded-lg text-rose-600 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center justify-between text-xs font-medium shadow-2xs">
          <div className="flex items-center space-x-2">
            <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button
            onClick={() => setSuccessMsg(null)}
            className="p-1 hover:bg-emerald-100 rounded-lg text-emerald-700 transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Scheduled Today */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Scheduled Today</span>
            <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
              <Calendar className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{todaySchedules.length}</span>
              <span className="text-xs text-slate-500">events</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Synchronized with FAO-56 model</p>
          </div>
        </div>

        {/* Card 2: Pending Actions */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Pending Actions</span>
            <div className="p-2.5 rounded-xl bg-amber-50 text-amber-600 border border-amber-100">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-amber-600">{pendingCount}</span>
              <span className="text-xs text-slate-500">runs queue</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Awaiting schedule pump execution</p>
          </div>
        </div>

        {/* Card 3: Completed Runs */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Completed Runs</span>
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-600">{completedCount}</span>
              <span className="text-xs text-slate-500">verified</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Software record & telemetry logged</p>
          </div>
        </div>

        {/* Card 4: Water to Dispense */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Water to Dispense</span>
            <div className="p-2.5 rounded-xl bg-teal-50 text-teal-600 border border-teal-100">
              <Droplets className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-bold text-teal-700">{totalWaterPending.toLocaleString()}</span>
              <span className="text-xs font-semibold text-teal-600">Liters</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Optimal root zone replenishment</p>
          </div>
        </div>
      </div>

      {/* Filter and Control Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-4 text-xs">
        {/* Status Pill Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-50 text-slate-700 border border-slate-200/80 font-semibold text-[11px]">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Filters:</span>
          </div>

          <button
            type="button"
            onClick={() => setShowOnlyToday(!showOnlyToday)}
            className={`px-3 py-1.5 rounded-xl font-semibold transition-all ${
              showOnlyToday
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 font-medium'
            }`}
          >
            Today's Only
          </button>

          {(['all', 'pending', 'completed', 'skipped', 'cancelled'] as const).map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setStatusFilter(status)}
              className={`capitalize px-3 py-1.5 rounded-xl font-semibold transition-all ${
                statusFilter === status
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 font-medium'
              }`}
            >
              {status}
            </button>
          ))}
        </div>

        {/* Date Range & Field Selectors */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-1.5 bg-slate-50 p-1 rounded-xl border border-slate-200/80">
            <span className="text-slate-500 text-[11px] font-semibold pl-2">From:</span>
            <input
              type="date"
              value={startDateFilter}
              onChange={(e) => setStartDateFilter(e.target.value)}
              className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800 text-xs focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            />
            <span className="text-slate-500 text-[11px] font-semibold">To:</span>
            <input
              type="date"
              value={endDateFilter}
              onChange={(e) => setEndDateFilter(e.target.value)}
              className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-slate-800 text-xs focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            />
            {(startDateFilter || endDateFilter) && (
              <button
                type="button"
                onClick={() => {
                  setStartDateFilter('');
                  setEndDateFilter('');
                }}
                className="text-[11px] font-semibold text-rose-600 hover:text-rose-700 hover:underline px-2"
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <label className="text-slate-500 text-[11px] font-semibold">Field:</label>
            <select
              value={selectedFieldId}
              onChange={(e) => setSelectedFieldId(e.target.value)}
              className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-slate-800 text-xs font-medium focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:outline-none shadow-2xs"
            >
              <option value="all">All Registered Fields</option>
              {fields.map((f) => (
                <option key={f.field_id} value={f.field_id}>
                  {f.name} ({f.crop_type})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Actuation Mode Notice Banner */}
      <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200/80 text-emerald-900 text-xs flex items-center justify-between gap-3 shadow-2xs">
        <div className="flex items-start md:items-center space-x-2.5">
          <Sparkles className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5 md:mt-0" />
          <span>
            <strong>Actuation Mode:</strong> Status transitions record software schedule execution and simulated actuator telemetry. Physical relay hardware integration runs in simulated mode until GPIO/LoRaWAN relays are wired.
          </span>
        </div>
      </div>

      {/* Schedule Table / List Card */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-2 bg-white">
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-bold text-slate-800">
              Irrigation Plan & Actuation Logs
            </h2>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
              {filteredSchedules.length}
            </span>
          </div>
          <div className="flex items-center space-x-3 text-[11px] text-slate-500 font-medium">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              <span>Pending</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span>Completed</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-400"></span>
              <span>Skipped</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-400"></span>
              <span>Cancelled</span>
            </span>
          </div>
        </div>

        {loading ? (
          <div className="py-16 text-center text-slate-400 space-y-3">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-emerald-600" />
            <p className="text-xs font-medium">Loading irrigation schedules...</p>
          </div>
        ) : filteredSchedules.length === 0 ? (
          <div className="py-16 text-center text-slate-400 space-y-3 px-4">
            <CalendarClock className="w-12 h-12 mx-auto text-slate-300" />
            <p className="text-sm font-bold text-slate-700">No irrigation schedules found matching your filter</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Generate an agronomic recommendation using AI or add a manual irrigation schedule for your field.
            </p>
            {fields.length > 0 && (
              <button
                type="button"
                onClick={() => handleGenerateSchedule(fields[0].field_id)}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition active:scale-95"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Auto-Generate for {fields[0].name}</span>
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200/80 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-5">Target Field & Crop</th>
                  <th className="py-3 px-4">Date & Time</th>
                  <th className="py-3 px-4">Duration & Volume</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Agronomic Reason</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredSchedules.map((item) => {
                  const targetField = fields.find((f) => f.field_id === item.field_id);
                  const isPending = item.status === 'pending';
                  const isCompleted = item.status === 'completed';
                  const isSkipped = item.status === 'skipped';
                  const isCancelled = item.status === 'cancelled';
                  const hasRainConflict =
                    (item.reason || '').toLowerCase().includes('rain') ||
                    (item.reason || '').toLowerCase().includes('weather');

                  return (
                    <tr
                      key={item.schedule_id}
                      className="hover:bg-slate-50/80 transition-colors"
                    >
                      {/* Target Field */}
                      <td className="py-3.5 px-5">
                        <div className="flex flex-col">
                          <span className="text-slate-900 font-bold text-sm">
                            {targetField ? targetField.name : item.field_id}
                          </span>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/60">
                              {targetField?.crop_type || 'Crop'}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {item.schedule_id}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Date & Time */}
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <span className="text-slate-800 font-semibold">
                            {(item.recommended_date || '').split('T')[0]}
                          </span>
                          <span className="text-[11px] text-slate-500 font-mono flex items-center gap-1 mt-0.5">
                            <Clock className="w-3 h-3 text-slate-400" />
                            {item.recommended_time || '06:00'} hrs
                          </span>
                        </div>
                      </td>

                      {/* Duration & Volume */}
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <span className="text-emerald-700 font-bold text-xs">
                            {item.water_quantity_liters?.toLocaleString()} Liters
                          </span>
                          <span className="text-[11px] text-slate-500 mt-0.5">
                            {item.duration_minutes} mins run
                          </span>
                        </div>
                      </td>

                      {/* Priority */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            item.priority === 'high'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : item.priority === 'medium'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          }`}
                        >
                          {item.priority || 'normal'}
                        </span>
                      </td>

                      {/* Agronomic Reason */}
                      <td className="py-3.5 px-4 max-w-xs">
                        <p className="text-xs text-slate-600 truncate" title={item.reason || ''}>
                          {item.reason || 'Optimal soil moisture balancing'}
                        </p>
                        {hasRainConflict && (
                          <span className="mt-1 inline-flex items-center gap-1 text-[10px] text-cyan-800 bg-cyan-50 px-2 py-0.5 rounded-full border border-cyan-200 font-semibold">
                            <CloudRain className="w-3 h-3 text-cyan-600" />
                            <span>Rain Forecast: Consider Deferral</span>
                          </span>
                        )}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                            isCompleted
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : isPending
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : isCancelled
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-slate-100 text-slate-600 border border-slate-200'
                          }`}
                        >
                          {isCompleted && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                          {isPending && <Clock className="w-3.5 h-3.5 text-amber-600" />}
                          {isSkipped && <XCircle className="w-3.5 h-3.5 text-slate-500" />}
                          {isCancelled && <Ban className="w-3.5 h-3.5 text-rose-600" />}
                          <span className="capitalize">{item.status}</span>
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-5 text-right">
                        <div className="flex items-center justify-end space-x-1.5">
                          {isPending ? (
                            <>
                              <button
                                type="button"
                                onClick={() => handleStatusChange(item.schedule_id, 'completed')}
                                title="Mark as Completed"
                                className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-2xs transition-colors flex items-center space-x-1"
                              >
                                <Check className="w-3 h-3" />
                                <span>Complete</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleStatusChange(item.schedule_id, 'skipped')}
                                title="Skip schedule"
                                className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 text-xs font-semibold transition-colors"
                              >
                                Skip
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingSchedule(item)}
                                title="Edit schedule"
                                className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-700 hover:bg-slate-100 transition-colors"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleStatusChange(item.schedule_id, 'cancelled')}
                                title="Cancel schedule"
                                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                              >
                                <Ban className="w-3.5 h-3.5" />
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                onClick={() => setEditingSchedule(item)}
                                title="Edit schedule"
                                className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-700 hover:bg-slate-100 transition-colors"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleStatusChange(item.schedule_id, 'pending')}
                                title="Re-open schedule"
                                className="text-xs font-semibold text-emerald-600 hover:text-emerald-800 hover:underline px-1"
                              >
                                Re-open
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteSchedule(item.schedule_id)}
                                title="Delete record"
                                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Manual Schedule Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl bg-white border border-slate-200 p-6 shadow-2xl text-slate-900 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                <CalendarClock className="w-5 h-5 text-emerald-600" />
                <span>Create Irrigation Schedule</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateManual} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Target Field *</label>
                <select
                  value={newSchedule.field_id}
                  onChange={(e) => setNewSchedule({ ...newSchedule, field_id: e.target.value })}
                  className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                  required
                >
                  {fields.map((f) => (
                    <option key={f.field_id} value={f.field_id}>
                      {f.name} ({f.crop_type}) - {f.location_name || f.field_id}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Date *</label>
                  <input
                    type="date"
                    value={newSchedule.recommended_date}
                    onChange={(e) => setNewSchedule({ ...newSchedule, recommended_date: e.target.value })}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Time (24h) *</label>
                  <input
                    type="time"
                    value={newSchedule.recommended_time}
                    onChange={(e) => setNewSchedule({ ...newSchedule, recommended_time: e.target.value })}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Duration (Minutes) *</label>
                  <input
                    type="number"
                    min="1"
                    value={newSchedule.duration_minutes}
                    onChange={(e) => setNewSchedule({ ...newSchedule, duration_minutes: Number(e.target.value) })}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Water Quantity (Liters) *</label>
                  <input
                    type="number"
                    min="1"
                    value={newSchedule.water_quantity_liters}
                    onChange={(e) => setNewSchedule({ ...newSchedule, water_quantity_liters: Number(e.target.value) })}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Priority</label>
                  <select
                    value={newSchedule.priority}
                    onChange={(e) => setNewSchedule({ ...newSchedule, priority: e.target.value })}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                  >
                    <option value="normal">Normal</option>
                    <option value="medium">Medium</option>
                    <option value="high">High (Urgent)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Agronomic Reason</label>
                  <input
                    type="text"
                    value={newSchedule.reason}
                    onChange={(e) => setNewSchedule({ ...newSchedule, reason: e.target.value })}
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    placeholder="e.g. Vegetative moisture replenishment"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition shadow-xs disabled:opacity-50"
                >
                  Save Schedule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Schedule Modal */}
      {editingSchedule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl bg-white border border-slate-200 p-6 shadow-2xl text-slate-900 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                <Edit2 className="w-5 h-5 text-emerald-600" />
                <span>Edit Irrigation Schedule ({editingSchedule.schedule_id})</span>
              </h3>
              <button
                type="button"
                onClick={() => setEditingSchedule(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdateSchedule} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Date *</label>
                  <input
                    type="date"
                    value={(editingSchedule.recommended_date || '').split('T')[0]}
                    onChange={(e) =>
                      setEditingSchedule({ ...editingSchedule, recommended_date: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Time (24h) *</label>
                  <input
                    type="time"
                    value={editingSchedule.recommended_time || '06:00'}
                    onChange={(e) =>
                      setEditingSchedule({ ...editingSchedule, recommended_time: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Duration (Minutes) *</label>
                  <input
                    type="number"
                    min="1"
                    value={editingSchedule.duration_minutes}
                    onChange={(e) =>
                      setEditingSchedule({
                        ...editingSchedule,
                        duration_minutes: Number(e.target.value),
                      })
                    }
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Water Quantity (Liters) *</label>
                  <input
                    type="number"
                    min="1"
                    value={editingSchedule.water_quantity_liters}
                    onChange={(e) =>
                      setEditingSchedule({
                        ...editingSchedule,
                        water_quantity_liters: Number(e.target.value),
                      })
                    }
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Priority</label>
                  <select
                    value={editingSchedule.priority || 'normal'}
                    onChange={(e) =>
                      setEditingSchedule({ ...editingSchedule, priority: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                  >
                    <option value="normal">Normal</option>
                    <option value="medium">Medium</option>
                    <option value="high">High (Urgent)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Agronomic Reason</label>
                  <input
                    type="text"
                    value={editingSchedule.reason || ''}
                    onChange={(e) =>
                      setEditingSchedule({ ...editingSchedule, reason: e.target.value })
                    }
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-slate-800 text-xs focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setEditingSchedule(null)}
                  className="px-4 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition shadow-xs disabled:opacity-50"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
