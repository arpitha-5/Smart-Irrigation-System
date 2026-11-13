import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  Sprout,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Droplets,
  CloudSun,
  ShieldCheck,
  Wheat,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { LanguageSelector } from '../components/common/LanguageSelector';
import { getErrorMessage } from '../services/api';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const [emailOrPhone, setEmailOrPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forgotModal, setForgotModal] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!emailOrPhone.trim()) {
      setError(t('auth.enterEmailOrPhone', 'Please enter your registered email address or mobile number.'));
      return;
    }
    if (!password) {
      setError(t('auth.enterPassword', 'Please enter your password.'));
      return;
    }

    setLoading(true);
    try {
      await login({
        email_or_phone: emailOrPhone.trim(),
        password,
      });
      navigate(from, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between selection:bg-emerald-500 selection:text-white">
      {/* Top Bar with Language Selector */}
      <header className="px-6 py-4 flex items-center justify-between max-w-7xl mx-auto w-full">
        <Link to="/" className="flex items-center space-x-2.5 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-700 to-emerald-500 flex items-center justify-center text-white shadow-sm shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            <Sprout className="w-6 h-6" />
          </div>
          <div>
            <span className="font-bold text-lg text-slate-900 tracking-tight block leading-none">
              AgriPulse
            </span>
            <span className="text-[11px] text-slate-400 font-medium">
              {t('common.appTagline', 'Smart Irrigation & Water Management')}
            </span>
          </div>
        </Link>

        <div className="flex items-center space-x-3">
          <LanguageSelector variant="navbar" />
        </div>
      </header>

      {/* Main Login Split Container */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="max-w-4xl w-full bg-white rounded-3xl border border-slate-200/80 shadow-xl overflow-hidden grid grid-cols-1 md:grid-cols-2">
          {/* Left Agricultural Hero Branding */}
          <div className="hidden md:flex flex-col justify-between p-10 bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-950 text-white relative overflow-hidden">
            <div className="absolute -right-16 -top-16 w-64 h-64 bg-emerald-500/10 rounded-full blur-2xl" />
            <div className="absolute -left-16 -bottom-16 w-64 h-64 bg-teal-500/10 rounded-full blur-2xl" />

            {/* Top Badge */}
            <div className="relative z-10 space-y-2">
              <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-700/60 border border-emerald-500/30 text-emerald-200">
                <Wheat className="w-3.5 h-3.5 text-emerald-300" />
                <span>{t('auth.farmerPortal', 'Farmer Intelligent Advisory Portal')}</span>
              </span>
              <h2 className="text-2xl lg:text-3xl font-extrabold tracking-tight leading-tight">
                Empowering Farmers with Predictive Water Intelligence
              </h2>
              <p className="text-xs text-emerald-100/80 leading-relaxed pt-1">
                Access real-time soil telemetry, live weather forecasts, ML-driven water schedules, and official crop reports.
              </p>
            </div>

            {/* Feature Pills */}
            <div className="relative z-10 space-y-3 my-8">
              <div className="flex items-center space-x-3 p-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs">
                <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-300">
                  <Droplets className="w-4 h-4" />
                </div>
                <div className="text-xs">
                  <div className="font-bold text-white">Targeted Water Scheduling</div>
                  <div className="text-emerald-200/70 text-[11px]">Save up to 40% water using IoT soil moisture</div>
                </div>
              </div>

              <div className="flex items-center space-x-3 p-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs">
                <div className="p-2 rounded-xl bg-teal-500/20 text-teal-300">
                  <CloudSun className="w-4 h-4" />
                </div>
                <div className="text-xs">
                  <div className="font-bold text-white">Live Weather Forecasts</div>
                  <div className="text-emerald-200/70 text-[11px]">Integrated rain forecasts prevent over-watering</div>
                </div>
              </div>

              <div className="flex items-center space-x-3 p-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs">
                <div className="p-2 rounded-xl bg-amber-500/20 text-amber-300">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div className="text-xs">
                  <div className="font-bold text-white">Secure Farmer Data</div>
                  <div className="text-emerald-200/70 text-[11px]">Encrypted session &amp; isolated farm plots</div>
                </div>
              </div>
            </div>

            {/* Bottom Tagline */}
            <div className="relative z-10 text-[11px] text-emerald-300/70">
              Trusted by farmers across Telangana, Andhra Pradesh, Karnataka, and Tamil Nadu.
            </div>
          </div>

          {/* Right Form Card */}
          <div className="p-8 lg:p-10 flex flex-col justify-center">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {t('auth.loginTitle', 'Welcome to AgriPulse')}
              </h2>
              <p className="text-xs text-slate-500 mt-1">
                {t('auth.loginSubtitle', 'Sign in to access your monitored farms, sensor telemetry, and irrigation advisory.')}
              </p>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  {t('auth.emailOrPhone', 'Email Address or Mobile Number')}
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    value={emailOrPhone}
                    onChange={(e) => setEmailOrPhone(e.target.value)}
                    placeholder="e.g. ramesh@farm.test or 9876543210"
                    className="w-full pl-9 pr-3 py-2.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium text-slate-800"
                    required
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-slate-700">
                    {t('auth.password', 'Password')}
                  </label>
                  <button
                    type="button"
                    onClick={() => setForgotModal(true)}
                    className="text-[11px] font-semibold text-emerald-600 hover:text-emerald-700 transition-colors"
                  >
                    {t('auth.forgotPassword', 'Forgot Password?')}
                  </button>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full pl-9 pr-10 py-2.5 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium text-slate-800"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center space-x-2 text-xs text-slate-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>{t('auth.rememberMe', 'Remember me')}</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-xs transition-colors flex items-center justify-center space-x-2 cursor-pointer disabled:opacity-50"
              >
                <span>{loading ? t('auth.signingIn', 'Signing In...') : t('auth.signIn', 'Sign In to Dashboard')}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>

            <div className="mt-6 pt-6 border-t border-slate-100 text-center text-xs text-slate-500">
              <span>{t('auth.noAccount', "Don't have an account yet?")} </span>
              <Link to="/signup" className="font-bold text-emerald-600 hover:text-emerald-700 underline underline-offset-2">
                {t('auth.createAccount', 'Create Account & Register Farm')}
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Forgot Password Helper Modal */}
      {forgotModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-xl space-y-3">
            <h3 className="text-sm font-bold text-slate-900">Reset Account Access</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              For security, farmer password resets can be performed by contacting your local agricultural extension officer
              or by logging in with your registered mobile phone number.
            </p>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setForgotModal(false)}
                className="px-4 py-1.5 bg-emerald-600 text-white rounded-xl text-xs font-semibold"
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="py-4 text-center text-[11px] text-slate-400">
        &copy; 2026 AgriPulse AI. All rights reserved &bull; Predictive Water Management System
      </footer>
    </div>
  );
};

export default LoginPage;
