import React, { useState } from 'react';
import {
  User,
  Phone,
  Mail,
  MapPin,
  Languages,
  ShieldCheck,
  Edit3,
  Save,
  CheckCircle2,
  Wheat,
  Activity,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage, SUPPORTED_LANGUAGES } from '../context/LanguageContext';
import { updateFarmerProfile } from '../services/api';
import { Link } from 'react-router-dom';

export const ProfilePage: React.FC = () => {
  const { farmer, refreshProfile } = useAuth();
  const { t, language, setLanguage, currentLanguage } = useLanguage();

  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: farmer?.name || '',
    phone: farmer?.phone || '',
    village: farmer?.village || '',
    district: farmer?.district || '',
    state: farmer?.state || 'Telangana',
    age: farmer?.age || undefined,
    contact_method: farmer?.contact_method || 'phone',
    preferred_language: farmer?.preferred_language || language,
  });

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setErrorMsg(null);
      await updateFarmerProfile({
        name: formData.name,
        phone: formData.phone,
        village: formData.village,
        district: formData.district,
        state: formData.state,
        age: formData.age ? Number(formData.age) : undefined,
        contact_method: formData.contact_method,
        preferred_language: formData.preferred_language,
      });

      if (formData.preferred_language && formData.preferred_language !== language) {
        setLanguage(formData.preferred_language as any);
      }

      await refreshProfile();
      setSuccessMsg(t('auth.profileUpdated', 'Farmer profile updated successfully!'));
      setIsEditing(false);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t('auth.farmerProfile', 'Farmer Profile')}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {t('auth.profileSubtitle', 'Manage your registered farm account, regional contact details, and language preferences.')}
          </p>
        </div>

        {!isEditing && (
          <button
            onClick={() => {
              setFormData({
                name: farmer?.name || '',
                phone: farmer?.phone || '',
                village: farmer?.village || '',
                district: farmer?.district || '',
                state: farmer?.state || 'Telangana',
                age: farmer?.age || undefined,
                contact_method: farmer?.contact_method || 'phone',
                preferred_language: farmer?.preferred_language || language,
              });
              setIsEditing(true);
            }}
            className="inline-flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>{t('common.edit', 'Edit Profile')}</span>
          </button>
        )}
      </div>

      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold">
          {errorMsg}
        </div>
      )}

      {/* Main Profile Card */}
      <div className="bg-white/95 backdrop-blur-xs rounded-3xl border border-slate-200/90 shadow-sm overflow-hidden">
        {/* Cover Banner */}
        <div className="h-28 bg-gradient-to-r from-emerald-800 via-emerald-700 to-teal-700 p-6 flex items-end relative">
          <div className="absolute top-4 right-4 flex items-center space-x-1 px-2.5 py-1 rounded-full bg-white/20 backdrop-blur-xs text-white text-[11px] font-bold border border-white/20">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-200" />
            <span>{t('auth.verifiedFarmer', 'Verified Farmer Account')}</span>
          </div>
        </div>

        <div className="px-6 pb-6 pt-0 relative">
          {/* Avatar and Main Identity */}
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 -mt-10 mb-6">
            <div className="flex items-end space-x-4">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-white font-black text-2xl flex items-center justify-center border-4 border-white shadow-md">
                {farmer?.name ? farmer.name.charAt(0).toUpperCase() : <User className="w-9 h-9" />}
              </div>
              <div className="pb-1">
                <h2 className="text-xl font-bold text-slate-900">{farmer?.name || 'Registered Farmer'}</h2>
                <p className="text-xs text-slate-500 flex items-center space-x-1 mt-0.5">
                  <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                  <span>
                    {[farmer?.village, farmer?.district, farmer?.state].filter(Boolean).join(', ') || 'Location not specified'}
                  </span>
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <div className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600">
                <span className="text-slate-400 text-[10px] block">Language</span>
                <span className="font-bold text-slate-800">{currentLanguage.nativeName}</span>
              </div>
              <div className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600">
                <span className="text-slate-400 text-[10px] block">Contact</span>
                <span className="font-bold text-slate-800 uppercase">{farmer?.contact_method || 'Phone'}</span>
              </div>
            </div>
          </div>

          {/* Edit Form OR View Details */}
          {isEditing ? (
            <form onSubmit={handleSave} className="space-y-4 pt-4 border-t border-slate-100">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {t('auth.fullName', 'Full Name')}
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {t('auth.mobileNumber', 'Mobile Number')}
                  </label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Village / Mandal</label>
                  <input
                    type="text"
                    value={formData.village}
                    onChange={(e) => setFormData({ ...formData, village: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">District</label>
                  <input
                    type="text"
                    value={formData.district}
                    onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">State</label>
                  <select
                    value={formData.state}
                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="Telangana">Telangana</option>
                    <option value="Andhra Pradesh">Andhra Pradesh</option>
                    <option value="Karnataka">Karnataka</option>
                    <option value="Tamil Nadu">Tamil Nadu</option>
                    <option value="Maharashtra">Maharashtra</option>
                    <option value="Other">Other State</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    {t('common.language', 'Preferred Language')}
                  </label>
                  <select
                    value={formData.preferred_language}
                    onChange={(e) => setFormData({ ...formData, preferred_language: e.target.value })}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    {SUPPORTED_LANGUAGES.map((langItem) => (
                      <option key={langItem.code} value={langItem.code}>
                        {langItem.nativeName} ({langItem.name})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  disabled={saving}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
                >
                  {t('common.cancel', 'Cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center space-x-1.5 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{saving ? t('common.loading', 'Saving...') : t('common.save', 'Save Changes')}</span>
                </button>
              </div>
            </form>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-100">
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Contact Information
                </h4>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center space-x-2 text-slate-700">
                    <Mail className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold text-slate-500">Email:</span>
                    <span className="font-medium text-slate-900">{farmer?.email || '—'}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-slate-700">
                    <Phone className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold text-slate-500">Phone:</span>
                    <span className="font-medium text-slate-900">{farmer?.phone || '—'}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-slate-700">
                    <MapPin className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold text-slate-500">Location:</span>
                    <span className="font-medium text-slate-900">
                      {[farmer?.village, farmer?.district, farmer?.state].filter(Boolean).join(', ') || '—'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Regional &amp; AI Preferences
                </h4>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center space-x-2 text-slate-700">
                    <Languages className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold text-slate-500">Default Advisory Language:</span>
                    <span className="font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                      {currentLanguage.nativeName} ({currentLanguage.code})
                    </span>
                  </div>
                  <div className="flex items-center space-x-2 text-slate-700">
                    <Activity className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span className="font-semibold text-slate-500">Advisory Alerts Delivery:</span>
                    <span className="font-medium text-slate-900 capitalize">
                      {farmer?.contact_method || 'Phone notification'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          to="/fields"
          className="p-5 rounded-2xl bg-white/95 border border-slate-200/90 shadow-2xs hover:shadow-md transition-all flex items-center justify-between group"
        >
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700 group-hover:scale-105 transition-transform">
              <Wheat className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">My Farm Fields</h4>
              <p className="text-xs text-slate-500">View registered crops and soil metrics</p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-1 transition-all" />
        </Link>

        <Link
          to="/recommendations"
          className="p-5 rounded-2xl bg-white/95 border border-slate-200/90 shadow-2xs hover:shadow-md transition-all flex items-center justify-between group"
        >
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-700 group-hover:scale-105 transition-transform">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">AI Irrigation Advisory</h4>
              <p className="text-xs text-slate-500">Check today's water recommendation</p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
        </Link>
      </div>
    </div>
  );
};

export default ProfilePage;
