import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sprout, ExternalLink, Sparkles, LogOut, Download, WifiOff, Bell, Menu } from 'lucide-react';
import { getHealth, seedDemoData, API_DOCS_URL } from '../../services/api';
import { useLanguage } from '../../context/LanguageContext';
import { useAuth } from '../../context/AuthContext';
import { usePWA } from '../../context/PWAContext';
import { LanguageSelector } from '../common/LanguageSelector';

interface NavbarProps {
  onRefresh?: () => void;
  onMenuToggle?: () => void;
  isSidebarOpen?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ onRefresh, onMenuToggle, isSidebarOpen = false }) => {
  const { t } = useLanguage();
  const { farmer, isAuthenticated, logout } = useAuth();
  const { isOnline, isInstallable, isInstalled, installApp } = usePWA();
  const navigate = useNavigate();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [seedNotice, setSeedNotice] = useState<string | null>(null);

  const checkStatus = async () => {
    try {
      const res = await getHealth();
      setBackendOnline(res?.status === 'ok');
    } catch {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSeed = async () => {
    if (!window.confirm('Load sample simulated demo data? All records will be clearly marked as is_demo/is_simulated.')) {
      return;
    }
    setSeeding(true);
    try {
      const res = await seedDemoData();
      setSeedNotice(res.status === 'already_seeded' ? 'Demo records already present.' : 'Demo records loaded!');
      setTimeout(() => setSeedNotice(null), 4000);
      if (onRefresh) onRefresh();
    } catch (err: any) {
      setSeedNotice('Failed to seed demo data');
      setTimeout(() => setSeedNotice(null), 4000);
    } finally {
      setSeeding(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="app-topbar">
      <div className="app-topbar-inner">
        <button
          type="button"
          className="app-menu-toggle"
          aria-label={isSidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={isSidebarOpen}
          aria-controls="app-navigation"
          onClick={onMenuToggle}
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="app-brand flex items-center space-x-3">
          <Link to="/" className="flex items-center space-x-2.5 group">
            <div className="app-brand-mark group-hover:bg-emerald-800 transition-colors">
              <Sprout className="w-6 h-6" />
            </div>
            <div>
              <span className="font-bold text-lg text-slate-800 tracking-tight block leading-tight">
                {t('common.appName', 'AgriPulse')} <span className="text-emerald-600 font-semibold text-sm"></span>
              </span>
              <span className="app-brand-tagline text-[11px] text-slate-500 font-medium">
                {t('common.appTagline', 'Smart Irrigation & Water Management')}
              </span>
            </div>
          </Link>
        </div>

        <div className="topbar-actions">
          {/* Prominent 5-Language Selector in Navbar */}
          <LanguageSelector variant="navbar" className="nav-language" />

          {/* PWA Connection Status Pill */}
          <div
            className={`nav-connection flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
              isOnline
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-amber-50 border-amber-300 text-amber-900'
            }`}
            title={isOnline ? 'Connected to internet' : 'Working offline with cached data'}
          >
            {isOnline ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span>{t('common.online', 'Online')}</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-amber-600" />
                <span>{t('common.offline', 'Offline PWA')}</span>
              </>
            )}
          </div>

          {/* PWA Install Button */}
          {!isInstalled && (
            <button
              onClick={installApp}
              title="Install AgriPulse Progressive Web App for offline field access"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-lg transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{t('common.installApp', 'Install App')}</span>
            </button>
          )}

          {/* Backend Status Pill */}
          <div
            className={`nav-backend flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
              backendOnline === true
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : backendOnline === false
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}
          >
            {backendOnline === true ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="nav-status-label">{t('nav.backendConnected', 'Backend Connected')}</span>
              </>
            ) : backendOnline === false ? (
              <>
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                <span className="nav-status-label">{t('nav.backendOffline', 'Backend Offline')}</span>
              </>
            ) : (
              <span>{t('common.loading', 'Checking...')}</span>
            )}
          </div>

          {/* Alerts & Risk Reports Quick Button */}
          <Link
            to="/alerts"
            title="View Active Alerts & Risk Reports"
            className="nav-alert inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border border-amber-200 bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-semibold transition-colors cursor-pointer"
          >
            <Bell className="w-3.5 h-3.5 text-amber-600" />
            <span>{t('nav.alerts', 'Alerts')}</span>
          </Link>

          {/* Seed Demo Action */}
          <button
            onClick={handleSeed}
            disabled={seeding || backendOnline === false}
            title="Seed simulated test dataset"
            className="nav-demo hidden sm:inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border border-emerald-200 hover:bg-emerald-50 text-emerald-800 text-xs font-medium transition-colors cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
            <span className="nav-demo-label">{seeding ? t('common.loading', 'Seeding...') : 'Demo Data'}</span>
          </button>

          {seedNotice && (
            <span className="nav-notice text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200">
              {seedNotice}
            </span>
          )}

          {/* Swagger link */}
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="nav-api text-xs text-slate-500 hover:text-emerald-700 font-medium hidden md:flex items-center space-x-1 px-2 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <span>{t('nav.swaggerApi', 'Swagger API')}</span>
            <ExternalLink className="w-3 h-3" />
          </a>

          {/* Farmer Authentication Profile Pill / Actions */}
          {isAuthenticated && farmer ? (
            <div className="nav-profile flex items-center space-x-2 pl-2 border-l border-slate-200">
              <Link
                to="/profile"
                title="View & Edit Farmer Profile"
                className="flex items-center space-x-2 bg-emerald-50 hover:bg-emerald-100/90 border border-emerald-200/90 rounded-xl px-2.5 py-1 text-xs transition-colors cursor-pointer group shadow-2xs"
              >
                <div className="w-6 h-6 rounded-lg bg-emerald-600 group-hover:bg-emerald-700 text-white font-bold flex items-center justify-center text-[11px] transition-colors">
                  {farmer.name.charAt(0).toUpperCase()}
                </div>
                <div className="hidden sm:block text-left">
                  <div className="font-bold text-slate-800 leading-none group-hover:text-emerald-900 transition-colors">
                    {farmer.name}
                  </div>
                  <div className="text-[10px] text-emerald-700 font-medium">
                    {t('auth.viewProfileShort', 'My Profile')} &bull; {[farmer.village, farmer.district].filter(Boolean)[0] || 'Farmer'}
                  </div>
                </div>
              </Link>
              <button
                onClick={handleLogout}
                title="Log out of session"
                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="nav-auth flex items-center space-x-2 pl-2 border-l border-slate-200">
              <Link
                to="/login"
                className="px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-emerald-700 hover:bg-slate-100 rounded-xl transition-colors"
              >
                {t('auth.login', 'Sign In')}
              </Link>
              <Link
                to="/signup"
                className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl shadow-xs transition-colors"
              >
                {t('auth.register', 'Register')}
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

