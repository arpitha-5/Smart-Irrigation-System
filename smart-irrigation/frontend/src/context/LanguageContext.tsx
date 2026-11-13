import React, { createContext, useContext, useState, type ReactNode } from 'react';

import en from '../locales/en.json';
import te from '../locales/te.json';
import hi from '../locales/hi.json';
import ta from '../locales/ta.json';
import kn from '../locales/kn.json';

export type LanguageCode = 'en' | 'te' | 'hi' | 'ta' | 'kn';

export interface LanguageInfo {
  code: LanguageCode;
  name: string;
  nativeName: string;
  flag: string;
  sarvamCode: string;
}

export const SUPPORTED_LANGUAGES: LanguageInfo[] = [
  { code: 'en', name: 'English', nativeName: 'English', flag: '🇬🇧', sarvamCode: 'en-IN' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు', flag: '🌾', sarvamCode: 'te-IN' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी', flag: '🇮🇳', sarvamCode: 'hi-IN' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்', flag: '🌴', sarvamCode: 'ta-IN' },
  { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ', flag: '🌱', sarvamCode: 'kn-IN' },
];

const TRANSLATIONS: Record<LanguageCode, any> = {
  en,
  te,
  hi,
  ta,
  kn,
};

const STORAGE_KEY = 'agripulse_language';

interface LanguageContextType {
  language: LanguageCode;
  setLanguage: (lang: LanguageCode) => void;
  currentLanguage: LanguageInfo;
  languages: LanguageInfo[];
  t: (key: string, fallback?: string, params?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<LanguageCode>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as LanguageCode | null;
      if (saved && (saved === 'en' || saved === 'te' || saved === 'hi' || saved === 'ta' || saved === 'kn')) {
        return saved;
      }
    } catch {
      // localStorage may fail in some environments
    }
    return 'en';
  });

  const setLanguage = (newLang: LanguageCode) => {
    setLanguageState(newLang);
    try {
      localStorage.setItem(STORAGE_KEY, newLang);
    } catch (e) {
      console.warn('Failed to save language preference:', e);
    }
  };

  const currentLanguage =
    SUPPORTED_LANGUAGES.find((l) => l.code === language) || SUPPORTED_LANGUAGES[0];

  const t = (key: string, fallback?: string, params?: Record<string, string | number>): string => {
    const keys = key.split('.');
    
    // Attempt lookup in active language
    let result: any = TRANSLATIONS[language];
    for (const k of keys) {
      if (result && typeof result === 'object' && k in result) {
        result = result[k];
      } else {
        result = undefined;
        break;
      }
    }

    // Fallback to English if not found
    if (result === undefined && language !== 'en') {
      let enResult: any = TRANSLATIONS.en;
      for (const k of keys) {
        if (enResult && typeof enResult === 'object' && k in enResult) {
          enResult = enResult[k];
        } else {
          enResult = undefined;
          break;
        }
      }
      result = enResult;
    }

    if (result === undefined) {
      result = fallback !== undefined ? fallback : key;
    }

    if (typeof result === 'string' && params) {
      Object.entries(params).forEach(([paramKey, val]) => {
        result = result.replace(new RegExp(`{${paramKey}}`, 'g'), String(val));
      });
    }

    return typeof result === 'string' ? result : fallback || key;
  };

  return (
    <LanguageContext.Provider
      value={{
        language,
        setLanguage,
        currentLanguage,
        languages: SUPPORTED_LANGUAGES,
        t,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
