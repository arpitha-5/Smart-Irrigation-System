import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { Farmer, Field, FarmerLoginPayload, FarmerRegisterPayload, FarmerUpdate } from '../types';
import { loginFarmer, registerFarmer, getCurrentUser, updateFarmerProfile } from '../services/api';
import { useLanguage, type LanguageCode } from './LanguageContext';

const TOKEN_KEY = 'agripulse_token';
const FARMER_KEY = 'agripulse_farmer';

interface AuthContextType {
  token: string | null;
  farmer: Farmer | null;
  user: (Farmer & { full_name?: string }) | null;
  fields: Field[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: FarmerLoginPayload) => Promise<void>;
  register: (payload: FarmerRegisterPayload) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
  updateProfile: (payload: FarmerUpdate) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { setLanguage } = useLanguage();
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [farmer, setFarmer] = useState<Farmer | null>(() => {
    try {
      const saved = localStorage.getItem(FARMER_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [fields, setFields] = useState<Field[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Sync preferred language from farmer profile if available
  const applyFarmerLanguage = (f: Farmer | null) => {
    if (f?.preferred_language) {
      const code = f.preferred_language.toLowerCase() as LanguageCode;
      if (['en', 'te', 'hi', 'ta', 'kn'].includes(code)) {
        setLanguage(code);
      }
    }
  };

  const refreshProfile = async () => {
    const curToken = localStorage.getItem(TOKEN_KEY);
    if (!curToken) {
      setFarmer(null);
      setFields([]);
      setIsLoading(false);
      return;
    }

    try {
      const data = await getCurrentUser();
      setFarmer(data.farmer);
      setFields(data.fields || []);
      localStorage.setItem(FARMER_KEY, JSON.stringify(data.farmer));
      applyFarmerLanguage(data.farmer);
    } catch (err) {
      console.warn('Session expired or invalid token:', err);
      // Remove stale token
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(FARMER_KEY);
      setToken(null);
      setFarmer(null);
      setFields([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshProfile();
  }, [token]);

  const login = async (payload: FarmerLoginPayload) => {
    const res = await loginFarmer(payload);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(FARMER_KEY, JSON.stringify(res.farmer));
    setToken(res.access_token);
    setFarmer(res.farmer);
    applyFarmerLanguage(res.farmer);
    await refreshProfile();
  };

  const register = async (payload: FarmerRegisterPayload) => {
    const res = await registerFarmer(payload);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(FARMER_KEY, JSON.stringify(res.farmer));
    setToken(res.access_token);
    setFarmer(res.farmer);
    applyFarmerLanguage(res.farmer);
    await refreshProfile();
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(FARMER_KEY);
    setToken(null);
    setFarmer(null);
    setFields([]);
  };

  const updateProfile = async (payload: FarmerUpdate) => {
    const updated = await updateFarmerProfile(payload);
    setFarmer(updated);
    localStorage.setItem(FARMER_KEY, JSON.stringify(updated));
    applyFarmerLanguage(updated);
    await refreshProfile();
  };

  const user = farmer ? { ...farmer, full_name: farmer.name } : null;

  return (
    <AuthContext.Provider
      value={{
        token,
        farmer,
        user,
        fields,
        isAuthenticated: !!token && !!farmer,
        isLoading,
        login,
        register,
        logout,
        refreshProfile,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
