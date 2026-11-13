import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sprout,
  User,
  Mail,
  Phone,
  Lock,
  Eye,
  EyeOff,
  Languages,
  MapPin,
  Map,
  Compass,
  Droplets,
  CloudSun,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Search,
  Check,
  Wheat,
  Activity,
  Layers,
  Navigation,
  Loader2,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage, SUPPORTED_LANGUAGES, type LanguageCode } from '../context/LanguageContext';
import { LanguageSelector } from '../components/common/LanguageSelector';
import { apiClient, getErrorMessage } from '../services/api';
import type { SearchedWeather, PlaceResult } from '../types';

export const SignupPage: React.FC = () => {
  const { register } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const navigate = useNavigate();

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // ── Step 1: Account Details ──
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // ── Step 2: Farmer Profile ──
  const [age, setAge] = useState<string>('');
  const [selectedLanguage, setSelectedLanguage] = useState<LanguageCode>(language);
  const [stateName, setStateName] = useState('Telangana');
  const [district, setDistrict] = useState('');
  const [village, setVillage] = useState('');
  const [contactMethod, setContactMethod] = useState('phone');

  // ── Step 3: Farm & Field Details ──
  const [farmName, setFarmName] = useState('');
  const [fieldName, setFieldName] = useState('');
  const [area, setArea] = useState<string>('2.5');
  const [areaUnit, setAreaUnit] = useState<'acres' | 'hectares' | 'sq_meters'>('acres');
  const [soilType, setSoilType] = useState('Loamy');
  const [soilPh, setSoilPh] = useState<string>('6.5');
  const [irrigationMethod, setIrrigationMethod] = useState('Drip');
  const [flowRateLpm, setFlowRateLpm] = useState<string>('250');
  const [cropType, setCropType] = useState('Rice');
  const [cropVariety, setCropVariety] = useState('');
  const [plantingDate, setPlantingDate] = useState('');
  const [growthStage, setGrowthStage] = useState('vegetative');

  // ── Step 4: Farm Location & Live Weather ──
  const [locationMode, setLocationMode] = useState<'gps' | 'manual'>('gps');
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [locationLabel, setLocationLabel] = useState<string>('');
  const [manualQuery, setManualQuery] = useState('');
  const [searchResults, setSearchResults] = useState<PlaceResult[]>([]);
  const [searchingPlaces, setSearchingPlaces] = useState(false);
  const [fetchingWeather, setFetchingWeather] = useState(false);
  const [weatherPreview, setWeatherPreview] = useState<SearchedWeather | null>(null);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [detectingGps, setDetectingGps] = useState(false);
  const [gpsStatus, setGpsStatus] = useState<string | null>(null);

  // ── Step 5: Review & Consent ──
  const [agreedTerms, setAgreedTerms] = useState(false);

  // Fetch live weather when coordinates change
  const fetchWeatherForCoords = async (lat: number, lon: number, label?: string) => {
    setFetchingWeather(true);
    setWeatherError(null);
    try {
      const { data } = await apiClient.get<SearchedWeather>('/weather/live-by-coords', {
        params: {
          latitude: lat,
          longitude: lon,
          location_name: label || undefined,
        },
      });
      setWeatherPreview(data);
    } catch (err) {
      console.warn('Weather fetch failed during onboarding:', err);
      setWeatherError('Live weather observation temporarily unavailable for these coordinates. You may still proceed with registration.');
    } finally {
      setFetchingWeather(false);
    }
  };

  // Step 2 Current GPS Location Detection & Auto-fill
  const handleStep2GpsLocation = () => {
    if (!navigator.geolocation) {
      setError('Browser geolocation is not supported by your device.');
      return;
    }

    setDetectingGps(true);
    setError(null);
    setGpsStatus(null);

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(4));
        const lon = parseFloat(pos.coords.longitude.toFixed(4));
        setLatitude(lat);
        setLongitude(lon);

        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=12&addressdetails=1`,
            { headers: { 'Accept-Language': 'en' } }
          );
          if (res.ok) {
            const data = await res.json();
            const addr = data.address || {};
            if (addr.village || addr.suburb || addr.town || addr.hamlet) {
              setVillage(addr.village || addr.suburb || addr.town || addr.hamlet);
            }
            if (addr.state_district || addr.county || addr.city) {
              setDistrict(addr.state_district || addr.county || addr.city);
            }
            if (addr.state) {
              const matchedState = ['Telangana', 'Andhra Pradesh', 'Karnataka', 'Tamil Nadu', 'Maharashtra'].find(
                (s) => addr.state.toLowerCase().includes(s.toLowerCase())
              );
              if (matchedState) {
                setStateName(matchedState);
              }
            }
            setGpsStatus(`📍 Location detected: ${data.name || addr.village || addr.city || ''} (${lat}, ${lon})`);
          } else {
            setGpsStatus(`📍 Coordinates locked: Lat ${lat}, Lon ${lon}`);
          }
        } catch (e) {
          setGpsStatus(`📍 Coordinates locked: Lat ${lat}, Lon ${lon}`);
        }

        const autoLabel = `${village || district || 'Farm Plot'} (${lat}, ${lon})`;
        setLocationLabel(autoLabel);
        fetchWeatherForCoords(lat, lon, autoLabel);
        setDetectingGps(false);
      },
      (err) => {
        console.warn('Geolocation denied or failed:', err);
        setError('Location permission denied or unavailable. Please enter details manually.');
        setDetectingGps(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  // Browser Geolocation
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError('Browser geolocation is not supported by your device. Please enter location manually.');
      setLocationMode('manual');
      return;
    }

    setFetchingWeather(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(4));
        const lon = parseFloat(pos.coords.longitude.toFixed(4));
        setLatitude(lat);
        setLongitude(lon);
        const autoLabel = `${village || district || 'Farm Plot'} (${lat}, ${lon})`;
        setLocationLabel(autoLabel);
        fetchWeatherForCoords(lat, lon, autoLabel);
      },
      (err) => {
        console.warn('Geolocation denied or failed:', err);
        setError('Location permission denied or unavailable. Please use manual location entry below.');
        setLocationMode('manual');
        setFetchingWeather(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  // Search places via backend geocoding
  const handleSearchPlaces = async () => {
    if (!manualQuery.trim()) return;
    setSearchingPlaces(true);
    setError(null);
    try {
      const { data } = await apiClient.get<PlaceResult[]>('/weather/geocode', {
        params: { q: manualQuery.trim(), limit: 5 },
      });
      setSearchResults(data);
      if (data.length === 0) {
        setError(`No locations found for "${manualQuery}". Try typing city or district name.`);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSearchingPlaces(false);
    }
  };

  const handleSelectPlace = (place: PlaceResult) => {
    setLatitude(place.latitude);
    setLongitude(place.longitude);
    setLocationLabel(place.label);
    setSearchResults([]);
    fetchWeatherForCoords(place.latitude, place.longitude, place.label);
  };

  // Step 1 Validation
  const validateStep1 = () => {
    setError(null);
    if (!name.trim()) return 'Please enter your full name.';
    if (!email.trim() || !email.includes('@')) return 'Please enter a valid email address.';
    const digits = phone.replace(/[^\d]/g, '');
    if (digits.length < 10) return 'Please enter a valid 10-digit mobile number.';
    if (password.length < 6) return 'Password must be at least 6 characters long.';
    if (password !== confirmPassword) return 'Passwords do not match.';
    return null;
  };

  // Step 2 Validation
  const validateStep2 = () => {
    setError(null);
    if (!village.trim() && !district.trim()) {
      return 'Please provide at least your village or district name.';
    }
    return null;
  };

  // Step 3 Validation
  const validateStep3 = () => {
    setError(null);
    if (area && parseFloat(area) <= 0) return 'Area must be greater than zero.';
    return null;
  };

  // Navigation between steps
  const handleNextStep = () => {
    setError(null);
    if (currentStep === 1) {
      const err = validateStep1();
      if (err) {
        setError(err);
        return;
      }
    } else if (currentStep === 2) {
      const err = validateStep2();
      if (err) {
        setError(err);
        return;
      }
    } else if (currentStep === 3) {
      const err = validateStep3();
      if (err) {
        setError(err);
        return;
      }
    } else if (currentStep === 4) {
      // Optional coordinates check
    }
    setCurrentStep((prev) => Math.min(prev + 1, 5));
  };

  const handlePrevStep = () => {
    setError(null);
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  // Final Registration Submission
  const handleFinalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreedTerms) {
      setError('Please accept the Terms of Service & Privacy Policy to complete registration.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const areaVal = area ? parseFloat(area) : undefined;
      const phVal = soilPh ? parseFloat(soilPh) : undefined;
      const flowVal = flowRateLpm ? parseFloat(flowRateLpm) : undefined;
      const ageVal = age ? parseInt(age, 10) : undefined;

      await register({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        password,
        preferred_language: selectedLanguage,
        state: stateName,
        district: district.trim(),
        village: village.trim(),
        age: ageVal,
        contact_method: contactMethod,
        farm_name: farmName.trim() || undefined,
        field_name: fieldName.trim() || undefined,
        area: areaVal,
        area_unit: areaUnit,
        soil_type: soilType,
        soil_ph: phVal,
        irrigation_method: irrigationMethod,
        pump_flow_rate_lpm: flowVal,
        crop_type: cropType,
        crop_variety: cropVariety.trim() || undefined,
        planting_date: plantingDate || undefined,
        growth_stage: growthStage,
        latitude: latitude ?? undefined,
        longitude: longitude ?? undefined,
        location_name: locationLabel || village || district || stateName,
      });

      // Redirect directly to dashboard
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const STEPS = [
    { num: 1, title: 'Account Details' },
    { num: 2, title: 'Farmer Profile' },
    { num: 3, title: 'Farm & Soil' },
    { num: 4, title: 'Location & Weather' },
    { num: 5, title: 'Review & Finish' },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between selection:bg-emerald-500 selection:text-white">
      {/* Header */}
      <header className="px-6 py-4 flex items-center justify-between max-w-7xl mx-auto w-full">
        <Link to="/" className="flex items-center space-x-2.5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-700 to-emerald-500 flex items-center justify-center text-white shadow-sm shadow-emerald-500/20">
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

        <div className="flex items-center space-x-4">
          <span className="text-xs text-slate-500 hidden sm:inline">
            Already registered?{' '}
            <Link to="/login" className="font-bold text-emerald-600 hover:text-emerald-700 underline">
              Sign In
            </Link>
          </span>
          <LanguageSelector variant="navbar" />
        </div>
      </header>

      {/* Main Multi-Step Form */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="max-w-2xl w-full bg-white rounded-3xl border border-slate-200/80 shadow-xl p-6 sm:p-10 space-y-6">
          {/* Progress Indicator */}
          <div>
            <div className="flex items-center justify-between mb-3 text-xs font-semibold text-slate-500">
              <span>Step {currentStep} of 5: <b className="text-emerald-800">{STEPS[currentStep - 1].title}</b></span>
              <span className="text-emerald-700 font-mono">{Math.round((currentStep / 5) * 100)}%</span>
            </div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden flex">
              <div
                className="bg-emerald-600 h-full rounded-full transition-all duration-300"
                style={{ width: `${(currentStep / 5) * 100}%` }}
              />
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: Account Details */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 1: Account Details</h2>
                <p className="text-xs text-slate-500">Create your secure farmer credentials.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Full Name <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Ramesh Kumar"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email Address <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="ramesh@farm.test"
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Mobile Phone Number <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="9876543210"
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                      required
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="At least 6 characters"
                      className="w-full pl-9 pr-10 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Confirm Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter password"
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                      required
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Farmer Profile & Regional Language */}
          {currentStep === 2 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 2: Farmer Profile &amp; Language</h2>
                <p className="text-xs text-slate-500">Configure your regional language and farming location.</p>
              </div>

              {/* Language Selection Grid */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center space-x-1.5">
                  <Languages className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Preferred Regional Language</span>
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {SUPPORTED_LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      type="button"
                      onClick={() => {
                        setSelectedLanguage(lang.code);
                        setLanguage(lang.code);
                      }}
                      className={`p-2.5 rounded-xl border text-center transition-all cursor-pointer ${
                        selectedLanguage === lang.code
                          ? 'border-emerald-600 bg-emerald-50 text-emerald-900 font-bold shadow-xs'
                          : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <div className="text-sm">{lang.flag}</div>
                      <div className="text-xs font-semibold mt-0.5">{lang.nativeName}</div>
                      <div className="text-[10px] text-slate-400">{lang.name}</div>
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  The application UI, AI voice audio, and advisories will be tailored to this language.
                </p>
              </div>

              {/* GPS Auto-Detection Button for Farmer Location */}
              <div className="p-3.5 rounded-2xl bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-50 border border-emerald-200/90 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs">
                <div className="flex items-center space-x-2.5">
                  <div className="w-8 h-8 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <MapPin className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-emerald-950">
                      Use Current GPS Location
                    </div>
                    <div className="text-[11px] text-emerald-700">
                      {gpsStatus || 'Automatically detect your village, district, state, and coordinates'}
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleStep2GpsLocation}
                  disabled={detectingGps}
                  className="px-3.5 py-1.5 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow-xs transition-all flex items-center space-x-1.5 cursor-pointer shrink-0"
                >
                  {detectingGps ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Detecting GPS...</span>
                    </>
                  ) : (
                    <>
                      <Navigation className="w-3.5 h-3.5 text-emerald-200" />
                      <span>📍 Auto-Detect Location</span>
                    </>
                  )}
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">State</label>
                  <select
                    value={stateName}
                    onChange={(e) => setStateName(e.target.value)}
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
                  <label className="block text-xs font-semibold text-slate-700 mb-1">District</label>
                  <input
                    type="text"
                    value={district}
                    onChange={(e) => setDistrict(e.target.value)}
                    placeholder="e.g. Warangal"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Village / Mandal</label>
                  <input
                    type="text"
                    value={village}
                    onChange={(e) => setVillage(e.target.value)}
                    placeholder="e.g. Geesugonda"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Farmer Age <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <input
                    type="number"
                    min="18"
                    max="110"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    placeholder="e.g. 45"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Preferred Contact Method
                  </label>
                  <select
                    value={contactMethod}
                    onChange={(e) => setContactMethod(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="phone">Direct Phone Call</option>
                    <option value="whatsapp">WhatsApp Message</option>
                    <option value="sms">SMS Text Alert</option>
                    <option value="email">Email</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Farm, Field Details & Soil Type */}
          {currentStep === 3 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 3: Farm &amp; Field Soil Profile</h2>
                <p className="text-xs text-slate-500">Provide details for accurate irrigation calculations.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Farm Name</label>
                  <input
                    type="text"
                    value={farmName}
                    onChange={(e) => setFarmName(e.target.value)}
                    placeholder="e.g. Krishna Green Farms"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Initial Field / Plot Name</label>
                  <input
                    type="text"
                    value={fieldName}
                    onChange={(e) => setFieldName(e.target.value)}
                    placeholder="e.g. North Paddy Plot"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>
              </div>

              {/* Area & Unit */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Field Area Size</label>
                  <input
                    type="number"
                    step="any"
                    min="0.1"
                    value={area}
                    onChange={(e) => setArea(e.target.value)}
                    placeholder="e.g. 2.5"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Measurement Unit</label>
                  <select
                    value={areaUnit}
                    onChange={(e) => setAreaUnit(e.target.value as any)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="acres">Acres (1 acre = 0.40 ha)</option>
                    <option value="hectares">Hectares (ha)</option>
                    <option value="sq_meters">Square Metres (m²)</option>
                  </select>
                </div>
              </div>

              {/* Soil Classification & pH */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Soil Classification Type
                  </label>
                  <select
                    value={soilType}
                    onChange={(e) => setSoilType(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="Sandy">Sandy (High infiltration, rapid drainage)</option>
                    <option value="Sandy loam">Sandy Loam (Good drainage, light)</option>
                    <option value="Loamy">Loamy (Balanced moisture retention - Optimal)</option>
                    <option value="Clay loam">Clay Loam (Moderate retention, fertile)</option>
                    <option value="Clay">Clay (High water retention, slow infiltration)</option>
                    <option value="Silty">Silty Soil</option>
                    <option value="Other">Other / Unknown</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Soil pH <span className="text-slate-400 font-normal">(Optional, 0 - 14)</span>
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="14"
                    value={soilPh}
                    onChange={(e) => setSoilPh(e.target.value)}
                    placeholder="e.g. 6.5"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>
              </div>

              {/* Irrigation System & Flow Rate */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Irrigation Method</label>
                  <select
                    value={irrigationMethod}
                    onChange={(e) => setIrrigationMethod(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="Drip">Drip Irrigation (High efficiency)</option>
                    <option value="Sprinkler">Sprinkler System</option>
                    <option value="Flood">Surface / Flood Irrigation</option>
                    <option value="Furrow">Furrow Irrigation</option>
                    <option value="Other">Other / Manual Hose</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Pump Flow Rate (LPM) <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      step="any"
                      min="1"
                      value={flowRateLpm}
                      onChange={(e) => setFlowRateLpm(e.target.value)}
                      placeholder="e.g. 250"
                      className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium font-bold text-slate-800"
                    />
                    <span className="absolute right-3 top-2 text-xs text-slate-400 font-semibold">LPM</span>
                  </div>
                </div>
              </div>

              {/* Crop & Growth Stage */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Current Crop</label>
                  <select
                    value={cropType}
                    onChange={(e) => setCropType(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="Rice">Rice (Paddy)</option>
                    <option value="Cotton">Cotton</option>
                    <option value="Maize">Maize (Corn)</option>
                    <option value="Wheat">Wheat</option>
                    <option value="Tomato">Tomato</option>
                    <option value="Groundnut">Groundnut (Peanut)</option>
                    <option value="Chilli">Chilli</option>
                    <option value="Other">Other Crop</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Variety <span className="text-slate-400 font-normal">(Optional)</span>
                  </label>
                  <input
                    type="text"
                    value={cropVariety}
                    onChange={(e) => setCropVariety(e.target.value)}
                    placeholder="e.g. BPT 5204"
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Growth Stage</label>
                  <select
                    value={growthStage}
                    onChange={(e) => setGrowthStage(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                  >
                    <option value="seedling">Seedling</option>
                    <option value="vegetative">Vegetative</option>
                    <option value="flowering">Flowering</option>
                    <option value="maturity">Maturity</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: Farm Location & Live Weather */}
          {currentStep === 4 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 4: Farm Location &amp; Live Weather</h2>
                <p className="text-xs text-slate-500">
                  Accurate coordinates enable hyper-local rain forecasts and automatic evapotranspiration calculations.
                </p>
              </div>

              {/* Location Mode Buttons */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setLocationMode('gps');
                    handleUseCurrentLocation();
                  }}
                  className={`p-3.5 rounded-2xl border text-left flex items-start space-x-3 transition-all cursor-pointer ${
                    locationMode === 'gps'
                      ? 'border-emerald-600 bg-emerald-50/60 text-emerald-950 shadow-xs'
                      : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <Compass className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-bold">Use Current GPS Location</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Detect farm coordinates via device sensor</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setLocationMode('manual')}
                  className={`p-3.5 rounded-2xl border text-left flex items-start space-x-3 transition-all cursor-pointer ${
                    locationMode === 'manual'
                      ? 'border-emerald-600 bg-emerald-50/60 text-emerald-950 shadow-xs'
                      : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <MapPin className="w-5 h-5 text-teal-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-bold">Search Location Manually</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">Search village, mandal, or district name</div>
                  </div>
                </button>
              </div>

              {/* Manual Search Input */}
              {locationMode === 'manual' && (
                <div className="space-y-2">
                  <div className="flex space-x-2">
                    <div className="relative flex-1">
                      <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                      <input
                        type="text"
                        value={manualQuery}
                        onChange={(e) => setManualQuery(e.target.value)}
                        placeholder="e.g. Warangal, Telangana or Hyderabad, IN"
                        className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-emerald-600 font-medium"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleSearchPlaces}
                      disabled={searchingPlaces}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold cursor-pointer disabled:opacity-50"
                    >
                      {searchingPlaces ? 'Searching...' : 'Find Coordinates'}
                    </button>
                  </div>

                  {/* Geocode Search Results List */}
                  {searchResults.length > 0 && (
                    <div className="border border-slate-200 rounded-xl divide-y divide-slate-100 max-h-40 overflow-y-auto bg-white shadow-xs">
                      {searchResults.map((p, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSelectPlace(p)}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-emerald-50 flex items-center justify-between cursor-pointer"
                        >
                          <div>
                            <span className="font-bold text-slate-800">{p.name}</span>
                            <span className="text-slate-500 text-[11px]"> ({p.state || p.country})</span>
                          </div>
                          <span className="font-mono text-[10px] text-emerald-700 font-semibold">
                            {p.latitude.toFixed(2)}, {p.longitude.toFixed(2)}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Coordinates Display */}
              {latitude !== null && longitude !== null && (
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <MapPin className="w-4 h-4 text-emerald-600 shrink-0" />
                    <div>
                      <span className="font-semibold text-slate-800">Coordinates: </span>
                      <span className="font-mono text-emerald-800 font-bold">
                        {latitude.toFixed(4)}° N, {longitude.toFixed(4)}° E
                      </span>
                      {locationLabel && (
                        <div className="text-[11px] text-slate-500">{locationLabel}</div>
                      )}
                    </div>
                  </div>
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                </div>
              )}

              {/* Live Weather Preview Card */}
              {fetchingWeather && (
                <div className="p-4 rounded-2xl bg-emerald-50/50 border border-emerald-200 text-center text-xs text-emerald-800 animate-pulse">
                  Fetching real-time weather observations for your coordinates...
                </div>
              )}

              {weatherError && (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>{weatherError}</span>
                </div>
              )}

              {weatherPreview && (
                <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-50 via-teal-50/40 to-white border border-emerald-200 shadow-xs space-y-3">
                  <div className="flex items-center justify-between border-b border-emerald-100 pb-2">
                    <div className="flex items-center space-x-2">
                      <CloudSun className="w-4 h-4 text-emerald-600" />
                      <span className="text-xs font-bold text-emerald-950 uppercase tracking-wide">
                        Live Weather at Farm
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">
                      {weatherPreview.source.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                    <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                      <div className="text-[10px] text-slate-400">Temperature</div>
                      <div className="text-base font-black text-slate-900">{weatherPreview.temperature.toFixed(1)}°C</div>
                    </div>
                    <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                      <div className="text-[10px] text-slate-400">Humidity</div>
                      <div className="text-base font-black text-slate-900">{weatherPreview.humidity}%</div>
                    </div>
                    <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                      <div className="text-[10px] text-slate-400">Wind Speed</div>
                      <div className="text-base font-black text-slate-900">{weatherPreview.wind_speed?.toFixed(1) || 0} m/s</div>
                    </div>
                    <div className="p-2.5 bg-white rounded-xl border border-emerald-100">
                      <div className="text-[10px] text-slate-400">Rainfall (1h)</div>
                      <div className="text-base font-black text-slate-900">{weatherPreview.rainfall.toFixed(1)} mm</div>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-600 flex items-center justify-between pt-1">
                    <span>Condition: <b>{(weatherPreview.condition || 'Clear').toUpperCase()}</b></span>
                    <span className="text-slate-400">
                      Observed: {new Date(weatherPreview.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 5: Review & Complete Registration */}
          {currentStep === 5 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 5: Review &amp; Complete Registration</h2>
                <p className="text-xs text-slate-500">Verify your details before creating your account.</p>
              </div>

              {/* Review Sections */}
              <div className="space-y-3 text-xs">
                {/* 1. Account */}
                <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">Farmer &amp; Account</div>
                    <div className="font-bold text-slate-900 text-sm">{name}</div>
                    <div className="text-slate-600">{email} &bull; {phone}</div>
                    <div className="text-slate-500 text-[11px]">
                      Language: <b>{SUPPORTED_LANGUAGES.find((l) => l.code === selectedLanguage)?.name}</b>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(1)}
                    className="text-[11px] font-semibold text-emerald-600 hover:text-emerald-700"
                  >
                    Edit
                  </button>
                </div>

                {/* 2. Farm & Field */}
                <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">Farm &amp; Plot Profile</div>
                    <div className="font-bold text-slate-900 text-sm">{fieldName || farmName || 'Main Farm Field'}</div>
                    <div className="text-slate-600">
                      {area} {areaUnit} &bull; Crop: <b>{cropType}</b> ({growthStage})
                    </div>
                    <div className="text-slate-500 text-[11px]">
                      Soil: <b>{soilType}</b> {soilPh ? `(pH ${soilPh})` : ''} &bull; Irrigation: <b>{irrigationMethod}</b> ({flowRateLpm || 250} LPM)
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(3)}
                    className="text-[11px] font-semibold text-emerald-600 hover:text-emerald-700"
                  >
                    Edit
                  </button>
                </div>

                {/* 3. Location */}
                <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 flex items-start justify-between">
                  <div className="space-y-0.5">
                    <div className="text-[10px] font-bold text-slate-400 uppercase">Farm Location &amp; Weather</div>
                    <div className="font-bold text-slate-900">
                      {locationLabel || `${village}, ${district}, ${stateName}`}
                    </div>
                    {latitude !== null && longitude !== null ? (
                      <div className="font-mono text-[11px] text-emerald-800">
                        {latitude.toFixed(4)}° N, {longitude.toFixed(4)}° E
                      </div>
                    ) : (
                      <div className="text-slate-400 text-[11px]">Coordinates not specified</div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(4)}
                    className="text-[11px] font-semibold text-emerald-600 hover:text-emerald-700"
                  >
                    Edit
                  </button>
                </div>
              </div>

              {/* Consent Checkbox */}
              <div className="pt-2">
                <label className="flex items-start space-x-2 text-xs text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={agreedTerms}
                    onChange={(e) => setAgreedTerms(e.target.checked)}
                    className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span>
                    I accept the <b>AgriPulse Terms of Service</b> and <b>Privacy Policy</b>. My farm telemetry will be
                    used solely for predictive irrigation guidance and water conservation.
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Form Actions Footer */}
          <div className="flex items-center justify-between pt-4 border-t border-slate-100">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handlePrevStep}
                className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 text-xs font-semibold cursor-pointer transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Previous</span>
              </button>
            ) : (
              <div />
            )}

            {currentStep < 5 ? (
              <button
                type="button"
                onClick={handleNextStep}
                className="inline-flex items-center space-x-1.5 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs cursor-pointer transition-colors"
              >
                <span>Continue</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinalSubmit}
                disabled={loading || !agreedTerms}
                className="inline-flex items-center space-x-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-md shadow-emerald-600/20 cursor-pointer transition-colors disabled:opacity-50"
              >
                <span>{loading ? 'Creating Account & Farm...' : 'Complete Registration'}</span>
                <Check className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-[11px] text-slate-400">
        &copy; 2026 AgriPulse AI. All rights reserved &bull; Predictive Water Management System
      </footer>
    </div>
  );
};

export default SignupPage;
