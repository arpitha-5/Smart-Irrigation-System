import React from 'react';
import { Link } from 'react-router-dom';
import {
  Sprout,
  Droplets,
  CloudRain,
  Cpu,
  ShieldCheck,
  Database,
  ArrowRight,
  TrendingUp,
  Layers,
  Activity,
  CheckCircle2,
} from 'lucide-react';
import { API_DOCS_URL } from '../services/api';

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col">
      {/* Top Header */}
      <header className="bg-white/80 backdrop-blur-md sticky top-0 z-30 border-b border-emerald-100">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-700 to-emerald-500 flex items-center justify-center text-white shadow-sm shadow-emerald-500/20">
              <Sprout className="w-6 h-6" />
            </div>
            <div>
              <span className="font-bold text-xl text-slate-900 tracking-tight block leading-none">
                AgriPulse <span className="text-emerald-600 font-semibold text-sm"></span>
              </span>
              <span className="text-xs text-slate-400 font-medium">Predictive Water Management</span>
            </div>
          </div>

          <nav className="hidden md:flex items-center space-x-6 text-sm font-medium text-slate-600">
            <a href="#features" className="hover:text-emerald-600 transition-colors">Features</a>
            <a href="#architecture" className="hover:text-emerald-600 transition-colors">How It Works</a>
            <a href="#benefits" className="hover:text-emerald-600 transition-colors">Benefits</a>
            <a href={API_DOCS_URL} target="_blank" rel="noreferrer" className="hover:text-emerald-600 transition-colors">API Docs</a>
          </nav>

          <div className="flex items-center space-x-3">
            <Link
              to="/dashboard"
              className="inline-flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm px-4 py-2 rounded-xl shadow-xs transition-colors"
            >
              <span>Open Dashboard</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-16 pb-20 lg:pt-24 lg:pb-32 bg-gradient-to-b from-emerald-50/60 via-slate-50 to-slate-50">
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="text-center max-w-3xl mx-auto">
            <div className="">
            
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.15]">
              AI-Powered Smart Irrigation &{' '}
              <span className="text-emerald-600">Predictive Water Management</span>
            </h1>
            <p className="mt-6 text-lg sm:text-xl text-slate-600 leading-relaxed font-normal">
              Empower sustainable agriculture with continuous real-time IoT soil moisture telemetry,
              automated OpenWeather integration, deterministic data-cleaning pipelines, and TimescaleDB time-series storage.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                to="/dashboard"
                className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-base px-6 py-3.5 rounded-xl shadow-md shadow-emerald-600/20 transition-all hover:scale-[1.02]"
              >
                <span>Launch Agriculture Dashboard</span>
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link
                to="/status"
                className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 bg-white hover:bg-slate-100 text-slate-700 font-semibold text-base px-6 py-3.5 rounded-xl border border-slate-200 shadow-xs transition-all"
              >
                <Activity className="w-5 h-5 text-emerald-600" />
                <span>Verify System & TimescaleDB</span>
              </Link>
            </div>
          </div>

          {/* Quick Metrics Banner */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-xs text-center">
              <div className="text-3xl font-extrabold text-emerald-700">100%</div>
              <div className="text-xs text-slate-500 font-medium mt-1">Audit-Preserving Cleaning</div>
            </div>
            <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-xs text-center">
              <div className="text-3xl font-extrabold text-emerald-700">TimescaleDB</div>
              <div className="text-xs text-slate-500 font-medium mt-1">Hypertables Partitioning</div>
            </div>
            <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-xs text-center">
              <div className="text-3xl font-extrabold text-emerald-700">REST &amp; MQTT</div>
              <div className="text-xs text-slate-500 font-medium mt-1">Dual IoT Telemetry Ingestion</div>
            </div>
            <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-xs text-center">
              <div className="text-3xl font-extrabold text-emerald-700">95+ Tests</div>
              <div className="text-xs text-slate-500 font-medium mt-1">Automated Test Suite</div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Cards Section */}
      <section id="features" className="py-20 bg-white border-y border-slate-200/80">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-bold text-emerald-600 tracking-wider uppercase">End-to-End Capabilities</span>
            <h2 className="text-3xl font-bold text-slate-900 mt-2">Engineered for Agricultural Precision</h2>
            <p className="text-slate-600 mt-3 text-sm">
              Comprehensive telemetry ingestion, field-level weather intelligence, and strict data-quality boundaries.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:border-emerald-300 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Droplets className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Soil Moisture &amp; Sensor Telemetry</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Accepts multi-parameter readings including volumetric soil moisture (0-100%), temperature, humidity, pH, rainfall, and water levels via authenticated REST endpoints and background MQTT subscribers.
              </p>
            </div>

            <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:border-emerald-300 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <CloudRain className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">OpenWeather Synchronization</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Fetches live field-specific meteorological conditions (ambient temperature, humidity, rainfall volume, wind speed) with built-in deduplication, timeouts, and graceful fallbacks.
              </p>
            </div>

            <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:border-emerald-300 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Rigorous Data Quality Pipeline</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Enforces physical domain boundaries, flags out-of-order observations, rejects corrupted inputs, and logs structured quality events for full auditable traceability without fabricating synthetic numbers.
              </p>
            </div>

            <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:border-emerald-300 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Database className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">TimescaleDB Hypertables</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Automatic time-series partitioning on timestamp columns with compound primary keys ensuring lightning-fast aggregation queries and horizontal scalability for millions of IoT points.
              </p>
            </div>

            <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:border-emerald-300 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Layers className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Relational Domain Hierarchy</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Clear foreign key relationships spanning Farmers &rarr; Fields &rarr; Crops &rarr; Sensors &rarr; Sensor Readings with cascading safety, unique constraints, and full CRUD endpoints.
              </p>
            </div>

            <div className="bg-slate-50 p-8 rounded-2xl border border-slate-200 hover:border-emerald-300 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <TrendingUp className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-2">Live Analytical Visualizations</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Interactive Recharts charts displaying soil moisture depletion curves, diurnal temperature patterns, rainfall distribution, and exportable CSV reports for agronomic analysis.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How it Works / Architecture */}
      <section id="architecture" className="py-20 bg-slate-50">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-bold text-emerald-600 tracking-wider uppercase">System Architecture</span>
            <h2 className="text-3xl font-bold text-slate-900 mt-2">How AgriPulse AI Operates</h2>
          </div>

          <div className="grid md:grid-cols-4 gap-6">
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs relative">
              <div className="text-xs font-bold text-emerald-600 mb-2">STEP 1</div>
              <h4 className="font-bold text-slate-900 mb-1">IoT Telemetry</h4>
              <p className="text-xs text-slate-500 leading-relaxed">
                Sensors broadcast soil moisture and field telemetry via HTTP POST or MQTT broker topic.
              </p>
            </div>
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs relative">
              <div className="text-xs font-bold text-emerald-600 mb-2">STEP 2</div>
              <h4 className="font-bold text-slate-900 mb-1">Quality Inspection</h4>
              <p className="text-xs text-slate-500 leading-relaxed">
                Data pipeline validates timestamps, value bounds, and flags anomalies before persistence.
              </p>
            </div>
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs relative">
              <div className="text-xs font-bold text-emerald-600 mb-2">STEP 3</div>
              <h4 className="font-bold text-slate-900 mb-1">Weather Correlation</h4>
              <p className="text-xs text-slate-500 leading-relaxed">
                Field coordinates trigger OpenWeather updates, linking ambient moisture and rain with soil states.
              </p>
            </div>
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs relative">
              <div className="text-xs font-bold text-emerald-600 mb-2">STEP 4</div>
              <h4 className="font-bold text-slate-900 mb-1">Time-Series Storage</h4>
              <p className="text-xs text-slate-500 leading-relaxed">
                TimescaleDB chunks observations into hypertables for instant dashboard retrieval and analysis.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Footer */}
      <footer className="mt-auto bg-emerald-950 text-emerald-200 py-12 border-t border-emerald-900">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white">
              <Sprout className="w-5 h-5" />
            </div>
            <span className="font-bold text-white text-lg">AgriPulse</span>
          </div>

          <p className="text-xs text-emerald-400">
            AI-Powered Smart Irrigation System &bull; Predictive Water Management &bull; 
          </p>

          <div className="flex items-center space-x-4">
            <Link
              to="/dashboard"
              className="text-xs font-semibold bg-emerald-700 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg transition-colors"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

function SparklesIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  );
}
