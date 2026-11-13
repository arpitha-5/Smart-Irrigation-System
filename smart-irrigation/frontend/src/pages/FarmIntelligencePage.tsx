import React, { useEffect, useState } from 'react';
import { AlertTriangle, Droplets, Leaf, RefreshCw, ShieldCheck } from 'lucide-react';
import { calculateWaterBudget, getCropStress, getDigitalTwin, getErrorMessage } from '../services/api';
import type { CropStressResponse, DigitalTwinResponse, WaterBudgetResponse } from '../types';

const healthStyles: Record<string, string> = {
  healthy: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  moderate: 'border-amber-200 bg-amber-50 text-amber-800',
  critical: 'border-rose-200 bg-rose-50 text-rose-800',
  unknown: 'border-slate-200 bg-slate-50 text-slate-700',
};

export const FarmIntelligencePage: React.FC = () => {
  const [twin, setTwin] = useState<DigitalTwinResponse | null>(null);
  const [stress, setStress] = useState<CropStressResponse | null>(null);
  const [budget, setBudget] = useState<WaterBudgetResponse | null>(null);
  const [water, setWater] = useState('100000');
  const [days, setDays] = useState('7');
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [twinData, stressData] = await Promise.all([getDigitalTwin(), getCropStress()]);
      setTwin(twinData);
      setStress(stressData);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const runBudget = async (event: React.FormEvent) => {
    event.preventDefault();
    setCalculating(true);
    setError(null);
    try {
      setBudget(await calculateWaterBudget({
        available_water_liters: Number(water),
        horizon_days: Number(days),
      }));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-emerald-700">Phase 1 intelligence</p>
          <h1 className="text-3xl font-bold mt-1">Farm Intelligence</h1>
          <p className="text-slate-600 mt-2 max-w-2xl">
            A live view of registered fields, explainable crop-stress indicators, and water allocation planning.
          </p>
        </div>
        <button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white">
          <RefreshCw size={16} /> Refresh telemetry
        </button>
      </header>

      {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {loading ? (
        <div className="card-style flex items-center gap-3 p-8 text-slate-600"><RefreshCw className="animate-spin" size={18} /> Loading stored farm telemetry...</div>
      ) : (
        <>
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xl font-bold flex items-center gap-2"><Leaf size={20} className="text-emerald-700" /> Digital twin</h2>
              <span className="text-sm text-slate-500">{twin?.live_fields ?? 0} fields with telemetry</span>
            </div>
            {!twin?.fields.length ? <div className="card-style p-6 text-slate-600">No registered fields are available for this account.</div> : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {twin.fields.map((field) => (
                  <article key={field.field_id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
                    <div className="flex items-start justify-between gap-3">
                      <div><h3 className="font-bold">{field.name}</h3><p className="text-sm opacity-80">{field.crop_type} · {field.field_id}</p></div>
                      <span className={`rounded-full border px-2 py-1 text-xs font-bold capitalize ${healthStyles[field.health] ?? healthStyles.unknown}`}>{field.health}</span>
                    </div>
                    <p className="mt-4 text-sm">{field.health_reason}</p>
                    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div><span className="block text-xs opacity-70">Moisture</span><strong>{field.latest_reading?.soil_moisture != null ? `${field.latest_reading.soil_moisture.toFixed(1)}%` : 'Unavailable'}</strong></div>
                      <div><span className="block text-xs opacity-70">Temperature</span><strong>{field.latest_reading?.temperature != null ? `${field.latest_reading.temperature.toFixed(1)}°C` : 'Unavailable'}</strong></div>
                      <div><span className="block text-xs opacity-70">Irrigation</span><strong className="capitalize">{field.irrigation_status.replace('_', ' ')}</strong></div>
                      <div><span className="block text-xs opacity-70">Trend</span><strong>{field.moisture_change != null ? `${field.moisture_change > 0 ? '+' : ''}${field.moisture_change.toFixed(1)} pts` : 'Unavailable'}</strong></div>
                    </div>
                    {field.latest_reading?.is_simulated && <p className="mt-3 text-xs font-semibold">This reading is marked simulated.</p>}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-xl font-bold flex items-center gap-2"><AlertTriangle size={20} className="text-amber-600" /> Crop stress indicators</h2>
            {(stress?.fields ?? []).length === 0 ? (
              <div className="card-style p-6 text-sm text-slate-600">
                Crop stress indicators will appear when registered fields have usable telemetry.
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {(stress?.fields ?? []).map((field) => (
                  <article key={field.field_id} className="card-style p-5">
                    <div className="flex items-center justify-between"><h3 className="font-bold">{field.field_name}</h3><span className="font-bold">{field.risk_level} · {field.risk_score}/100</span></div>
                    <div className="mt-3 h-2 rounded-full bg-slate-100"><div className={`h-2 rounded-full ${field.risk_score >= 75 ? 'bg-rose-500' : field.risk_score >= 50 ? 'bg-orange-500' : field.risk_score >= 25 ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ width: `${field.risk_score}%` }} /></div>
                    <ul className="mt-4 space-y-1 text-sm text-slate-600">{field.reasons.map((reason) => <li key={reason}>• {reason}</li>)}</ul>
                    <p className="mt-3 text-sm font-semibold text-emerald-800">{field.recommended_actions[0]}</p>
                  </article>
                ))}
              </div>
            )}
            <p className="mt-3 text-xs text-slate-500">These are decision-support indicators from stored telemetry, not disease diagnoses or guaranteed predictions.</p>
          </section>

          <section className="grid gap-5 lg:grid-cols-[320px_1fr]">
            <form onSubmit={runBudget} className="card-style p-5 space-y-4">
              <h2 className="text-xl font-bold flex items-center gap-2"><Droplets size={20} className="text-sky-700" /> Water budget</h2>
              <label className="block text-sm font-semibold">Available water (liters)<input className="mt-1 w-full border p-2" type="number" min="1" value={water} onChange={(event) => setWater(event.target.value)} required /></label>
              <label className="block text-sm font-semibold">Planning horizon (days)<input className="mt-1 w-full border p-2" type="number" min="1" max="30" value={days} onChange={(event) => setDays(event.target.value)} required /></label>
              <button disabled={calculating} className="w-full rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white disabled:opacity-60">{calculating ? 'Calculating...' : 'Calculate allocation'}</button>
              <p className="text-xs text-slate-500">Planning estimate based on crop, area, and latest moisture. It does not write schedules or replace field measurements.</p>
            </form>
            <div className="card-style p-5">
              {!budget ? <div className="flex h-full min-h-40 items-center justify-center text-center text-slate-500"><ShieldCheck className="mr-2" size={18} /> Enter water capacity to see field priorities.</div> : (
                <>
                  <div className="grid gap-3 sm:grid-cols-4">{[['Available', budget.available_water_liters], ['Demand', budget.estimated_demand_liters], ['Allocated', budget.allocated_water_liters], ['Shortage', budget.shortage_liters]].map(([label, value]) => <div key={label} className="rounded-lg bg-slate-50 p-3"><span className="block text-xs text-slate-500">{label}</span><strong>{Number(value).toLocaleString()} L</strong></div>)}</div>
                  <div className="mt-5 divide-y">{budget.allocations.map((item) => <div key={item.field_id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><strong>{item.field_name}</strong><p className="text-xs capitalize text-slate-500">{item.priority} priority · {item.reason}</p></div><span className="text-sm font-semibold">{item.allocated_liters.toLocaleString()} / {item.estimated_demand_liters.toLocaleString()} L</span></div>)}</div>
                  <p className="mt-4 text-xs text-slate-500">{budget.assumptions.join(' ')}</p>
                </>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
};
