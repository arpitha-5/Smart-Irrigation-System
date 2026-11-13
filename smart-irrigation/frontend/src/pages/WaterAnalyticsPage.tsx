import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Download, Droplets, RefreshCw, TrendingDown } from 'lucide-react';
import { getErrorMessage, getFarmerDashboard, exportWaterAnalyticsToCsv } from '../services/api';
import type { FarmerDashboard } from '../types';

type Period = 'today' | 'week' | 'month';

const periodValues: Record<Period, { label: string; key: 'daily' | 'weekly' | 'monthly' }> = {
  today: { label: 'Today', key: 'daily' },
  week: { label: 'Past 7 days', key: 'weekly' },
  month: { label: 'Past 30 days', key: 'monthly' },
};

function formatLiters(value?: number | null): string {
  return value == null ? 'Unavailable' : `${value.toLocaleString()} L`;
}

export const WaterAnalyticsPage: React.FC = () => {
  const [dashboard, setDashboard] = useState<FarmerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>('today');

  const loadAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);
      setDashboard(await getFarmerDashboard());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAnalytics();
  }, []);

  const analytics = dashboard?.water_analytics;
  const selectedEstimate = analytics
    ? analytics[`${periodValues[period].key}_schedule_volume_estimate_liters`]
    : null;
  const metrics = useMemo(() => [
    { title: 'Completed Today', value: formatLiters(analytics?.daily_schedule_volume_estimate_liters), note: 'Completed schedule volume estimate' },
    { title: 'Past 7 Days', value: formatLiters(analytics?.weekly_schedule_volume_estimate_liters), note: 'Completed schedule volume estimate' },
    { title: 'Past 30 Days', value: formatLiters(analytics?.monthly_schedule_volume_estimate_liters), note: 'Completed schedule volume estimate' },
    { title: 'Water Saved vs Flood', value: formatLiters(analytics?.baseline_comparison.water_saved_liters), note: 'Estimated against the stated flood-irrigation baseline' },
  ], [analytics]);

  const fieldRows = analytics?.field_breakdown ?? [];
  const hasData = Boolean(analytics && (
    analytics.daily_schedule_volume_estimate_liters != null
    || analytics.weekly_schedule_volume_estimate_liters != null
    || analytics.monthly_schedule_volume_estimate_liters != null
    || analytics.baseline_comparison.water_saved_liters != null
    || fieldRows.length
  ));

  return (
    <div className="water-analytics-page space-y-6">
      <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="h-11 w-11 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
            <Droplets className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Water Usage Analytics</h1>
            <p className="mt-1 text-sm text-slate-500">
              Review recorded irrigation plans and clearly labeled volume estimates for your farm.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {analytics && (
            <button
              onClick={() => exportWaterAnalyticsToCsv(analytics)}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold"
            >
              <Download className="w-4 h-4" /> Export CSV
            </button>
          )}
          <button
            onClick={() => void loadAnalytics()}
            disabled={loading}
            aria-label="Refresh water analytics"
            className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Water volume summary</h2>
            <p className="mt-1 text-xs text-slate-500">
              Completed schedule quantities are estimates, not measured water usage. Flow-meter totals are shown only when the API provides them.
            </p>
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Analytics period">
            {(Object.keys(periodValues) as Period[]).map((value) => (
              <button
                key={value}
                onClick={() => setPeriod(value)}
                aria-pressed={period === value}
                className={`px-3 py-2 rounded-lg text-xs font-semibold border transition-colors ${
                  period === value
                    ? 'border-emerald-700 bg-emerald-700 text-white'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {periodValues[value].label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {metrics.map((metric, index) => (
            <article key={metric.title} className="min-w-0 min-h-[142px] rounded-xl border border-slate-200 bg-slate-50/70 p-4 flex flex-col">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold text-slate-600">{metric.title}</h3>
                {index === 3 && <TrendingDown className="h-4 w-4 text-emerald-700" />}
              </div>
              <p className="mt-3 text-xl font-bold text-slate-900 break-words">{loading ? 'Loading…' : metric.value}</p>
              <p className="mt-auto pt-2 text-[11px] leading-relaxed text-slate-500">{metric.note}</p>
            </article>
          ))}
        </div>

        <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-xs text-blue-900">
          <strong>{periodValues[period].label} estimate:</strong> {formatLiters(selectedEstimate)}.
          {' '}Savings are estimated using the recorded completed schedule quantities and the baseline description below; they are not metered measurements.
          {analytics?.baseline_comparison.baseline_description && (
            <p className="mt-2 text-blue-800">{analytics.baseline_comparison.baseline_description}</p>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="text-base font-bold text-slate-900">Field Water Distribution</h2>
            <p className="mt-1 text-xs text-slate-500">Compare available completed volume with planned irrigation for each field.</p>
          </div>
          <span className="text-[11px] font-medium text-slate-500">Measured values and schedule estimates are identified separately</span>
        </div>

        {fieldRows.length ? (
          <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
            {fieldRows.map((field) => {
              const isMeasured = field.actual_liters != null;
              const volume = field.actual_liters ?? field.completed_schedule_volume_estimate_liters;
              const progress = field.planned_liters > 0 && volume != null
                ? Math.min((volume / field.planned_liters) * 100, 100)
                : 0;
              return (
                <article key={field.field_id} className="min-w-0 rounded-xl border border-slate-200 p-4">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-sm text-slate-900 truncate">{field.field_name}</h3>
                      <p className="mt-0.5 text-[11px] text-slate-500">{field.field_id}</p>
                    </div>
                    <span className={`w-fit px-2 py-1 rounded-md text-[10px] font-semibold ${
                      isMeasured ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'
                    }`}>
                      {isMeasured ? 'Measured' : volume == null ? 'No completed data' : 'Estimate'}
                    </span>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">{isMeasured ? 'Actual water volume' : 'Completed volume estimate'}</p>
                      <p className="mt-1 text-sm font-bold text-slate-900">{formatLiters(volume)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">Planned volume</p>
                      <p className="mt-1 text-sm font-bold text-slate-900">{formatLiters(field.planned_liters)}</p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label={`${field.field_name} volume compared with plan`} aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
                      <div className="h-full rounded-full bg-emerald-600 transition-all" style={{ width: `${progress}%` }} />
                    </div>
                    <p className="mt-1.5 text-[10px] text-slate-500">
                      {volume == null
                        ? 'No completed volume is available for comparison.'
                        : field.planned_liters > 0
                          ? `${Math.round(progress)}% of planned volume${volume > field.planned_liters ? ' (bar capped at 100%)' : ''}`
                          : 'No planned volume available for comparison.'}
                    </p>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="mt-5 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
            <Droplets className="mx-auto h-7 w-7 text-slate-400" />
            <h3 className="mt-2 text-sm font-semibold text-slate-800">{loading ? 'Loading field records…' : 'No water records available'}</h3>
            <p className="mt-1 text-xs text-slate-500">
              Completed schedule estimates and planned volumes will appear here when the authenticated dashboard API returns them.
            </p>
          </div>
        )}

        {!hasData && !loading && !error && (
          <p className="mt-4 text-xs text-slate-500">No measured flow data is available. This view does not substitute sample values.</p>
        )}
      </section>
    </div>
  );
};
