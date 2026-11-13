import React from 'react';
import { WifiOff, RefreshCw, ArrowLeft, Droplets, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { usePWA } from '../context/PWAContext';
import { useLanguage } from '../context/LanguageContext';

export const OfflinePage: React.FC = () => {
  const { isOnline } = usePWA();
  const { t } = useLanguage();

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-3xl shadow-xl border border-emerald-100 p-8 text-center space-y-6">
        <div className="w-20 h-20 mx-auto rounded-3xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600 shadow-inner">
          <WifiOff className="w-10 h-10" />
        </div>

        <div className="space-y-2">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
            {isOnline ? 'Network Restored' : 'Offline Mode Active'}
          </span>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            {isOnline ? 'You Are Back Online!' : 'You Are Currently Offline'}
          </h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            {isOnline
              ? 'Your internet connection has been restored. You can now access real-time live sensor telemetry, live weather forecasts, and generate AI recommendations.'
              : 'AgriPulse is functioning in offline mode with cached farm data and local storage. Reconnect to the internet to fetch fresh sensor telemetry and live weather updates.'}
          </p>
        </div>

        <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200/60 text-left space-y-2">
          <div className="flex items-center space-x-2 text-xs font-bold text-emerald-900">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <span>PWA Offline Capabilities</span>
          </div>
          <ul className="text-xs text-emerald-800/80 space-y-1 list-disc list-inside">
            <li>View previously loaded farm dashboards &amp; fields</li>
            <li>Inspect cached crop profiles and irrigation schedules</li>
            <li>Automatic synchronization when network reconnects</li>
          </ul>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={() => window.location.reload()}
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Check Connection &amp; Reload</span>
          </button>
          <Link
            to="/dashboard"
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs rounded-xl transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Return to Dashboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
