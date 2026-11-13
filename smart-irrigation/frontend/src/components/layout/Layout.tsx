import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { WifiOff } from 'lucide-react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { AIAssistantWidget } from '../assistant/AIAssistantWidget';
import { usePWA } from '../../context/PWAContext';
import { useLanguage } from '../../context/LanguageContext';

export const Layout: React.FC = () => {
  const { isOnline } = usePWA();
  const { t } = useLanguage();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!sidebarOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSidebarOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sidebarOpen]);

  return (
    <div className="app-shell">
      <Navbar
        isSidebarOpen={sidebarOpen}
        onMenuToggle={() => setSidebarOpen((open) => !open)}
      />
      {!isOnline && (
        <div className="bg-amber-50 text-amber-900 text-xs px-4 py-2 font-medium flex items-center justify-center space-x-2 border-b border-amber-200">
          <WifiOff className="w-4 h-4 shrink-0" />
          <span>
            {t('pwa.offlineBanner', 'You are currently offline. Showing cached farm telemetry and field records on this device.')}
          </span>
        </div>
      )}
      <div className={`app-workspace${isOnline ? '' : ' is-offline'}`}>
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <button
          type="button"
          className={`app-backdrop${sidebarOpen ? ' is-visible' : ''}`}
          aria-label="Close navigation menu"
          onClick={() => setSidebarOpen(false)}
          tabIndex={sidebarOpen ? 0 : -1}
        />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
      <AIAssistantWidget />
    </div>
  );
};
