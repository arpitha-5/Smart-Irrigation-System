import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity,
  BarChart2,
  Bell,
  Brain,
  CalendarClock,
  CloudRain,
  Cpu,
  FileText,
  LayoutDashboard,
  MapPin,
  Settings,
  ShieldCheck,
  Sparkles,
  Sprout,
  Users,
  Wheat,
  X,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { t } = useLanguage();

  const groups = [
    {
      label: 'Overview',
      items: [
        { to: '/dashboard', label: t('nav.dashboard', 'Dashboard'), icon: LayoutDashboard },
      ],
    },
    {
      label: 'Farm Operations',
      items: [
        { to: '/schedules', label: t('nav.schedules', 'Irrigation Schedules'), icon: CalendarClock },
        { to: '/fields', label: t('nav.fieldMonitoring', 'Field Monitoring'), icon: MapPin },
        { to: '/farmers', label: t('nav.farmers', 'Farmers'), icon: Users },
        { to: '/crops', label: t('nav.crops', 'Crops'), icon: Wheat },
      ],
    },
    {
      label: 'Insights',
      items: [
        { to: '/intelligence', label: t('nav.intelligence', 'Farm Intelligence'), icon: Brain },
        { to: '/analytics', label: t('nav.analytics', 'Water Analytics'), icon: BarChart2 },
        { to: '/recommendations', label: t('nav.aiAdvisory', 'AI Advisory'), icon: Sparkles },
        { to: '/weather', label: t('nav.weather', 'Weather Data'), icon: CloudRain },
      ],
    },
    {
      label: 'Data & System',
      items: [
        { to: '/sensors', label: t('nav.sensors', 'Sensors'), icon: Cpu },
        { to: '/readings', label: t('nav.readings', 'Readings History'), icon: Activity },
        { to: '/alerts', label: t('nav.alerts', 'Alerts & Notifications'), icon: Bell },
        { to: '/reports', label: t('nav.reports', 'Field Reports'), icon: FileText },
        { to: '/data-quality', label: t('nav.dataQuality', 'Data Quality'), icon: ShieldCheck },
        { to: '/status', label: t('nav.systemStatus', 'System Status'), icon: Settings },
      ],
    },
  ];

  return (
    <aside id="app-navigation" className={`site-sidebar${isOpen ? ' is-open' : ''}`} aria-label="Main navigation">
      <div className="sidebar-brand">
        <NavLink to="/" onClick={onClose} className="sidebar-brand-link">
          <span className="sidebar-brand-mark" aria-hidden="true">
            <Sprout className="h-6 w-6" />
          </span>
          <span className="sidebar-brand-copy">
            <span className="sidebar-brand-name">AgriPulse</span>
            <span className="sidebar-brand-subtitle">Smart Irrigation &amp; Water Management</span>
          </span>
        </NavLink>
        <button type="button" className="sidebar-close-button" aria-label="Close navigation menu" onClick={onClose}>
          <X className="w-4 h-4" />
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Application sections">
        {groups.map((group) => (
          <section className="sidebar-group" key={group.label} aria-label={group.label}>
            <h2 className="sidebar-section-label">{group.label}</h2>
            <div className="sidebar-group-items">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={onClose}
                    className={({ isActive }) => `sidebar-link${isActive ? ' is-active' : ''}`}
                  >
                    <Icon className="sidebar-link-icon" aria-hidden="true" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </section>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-title">AgriPulse IoT</div>
        <div className="sidebar-feature-list" aria-label="Platform capabilities">
          <span>IoT Ingestion</span>
          <span>Relational Data</span>
          <span>TimescaleDB</span>
          <span>Data Quality</span>
        </div>
      </div>
    </aside>
  );
};
