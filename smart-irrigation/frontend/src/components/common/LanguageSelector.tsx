import React, { useState, useRef, useEffect } from 'react';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { useLanguage, type LanguageCode } from '../../context/LanguageContext';

interface LanguageSelectorProps {
  variant?: 'navbar' | 'prominent' | 'compact';
  className?: string;
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  variant = 'navbar',
  className = '',
}) => {
  const { language, setLanguage, currentLanguage, languages } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (code: LanguageCode) => {
    setLanguage(code);
    setIsOpen(false);
  };

  if (variant === 'prominent') {
    return (
      <div className={`language-selector-prominent bg-white p-4 rounded-2xl border border-slate-200 shadow-xs text-slate-800 ${className}`}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-700">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-emerald-800">
                Farmer Language Preference / రైతు భాష / किसान भाषा
              </div>
              <div className="text-sm font-medium text-slate-600 mt-0.5">
                Selected: <span className="font-bold text-slate-900">{currentLanguage.nativeName} ({currentLanguage.name})</span>
              </div>
            </div>
          </div>

          {/* 5 Language Quick Switch Buttons */}
          <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
            {languages.map((lang) => {
              const isSelected = lang.code === language;
              return (
                <button
                  key={lang.code}
                  onClick={() => handleSelect(lang.code)}
                  aria-pressed={isSelected}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-700 border-emerald-700 text-white font-bold'
                      : 'bg-white border-slate-200 hover:bg-emerald-50 text-slate-700 hover:text-emerald-800'
                  }`}
                  title={`${lang.name} (${lang.nativeName})`}
                >
                  <span>{lang.flag}</span>
                  <span>{lang.nativeName}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // Standard Navbar dropdown
  return (
    <div className={`relative inline-block text-left ${className}`} ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-1.5 text-xs font-semibold rounded-xl border border-emerald-200 bg-emerald-50/70 hover:bg-emerald-100 text-emerald-900 shadow-2xs transition-all cursor-pointer"
        aria-expanded={isOpen}
        aria-haspopup="true"
        title="Change Language / భాషను ఎంచుకోండి / भाषा बदलें"
      >
        <Globe className="w-4 h-4 text-emerald-700" />
        <span className="text-sm">{currentLanguage.flag}</span>
        <span className="font-medium tracking-tight text-slate-800">{currentLanguage.nativeName}</span>
        <span className="text-[10px] text-slate-500 uppercase">({currentLanguage.code})</span>
        <ChevronDown className="w-3.5 h-3.5 text-emerald-700 transition-transform duration-200" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-52 rounded-xl bg-white shadow-xl border border-slate-200 ring-1 ring-black/5 z-50 py-1.5 focus:outline-hidden animate-in fade-in zoom-in-95 duration-100">
          <div className="px-3 py-1.5 border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Select Language / భాష ఎంపిక
          </div>
          {languages.map((lang) => {
            const isSelected = lang.code === language;
            return (
              <button
                key={lang.code}
                onClick={() => handleSelect(lang.code)}
                className={`w-full flex items-center justify-between px-3 py-2 text-xs font-medium transition-colors text-left cursor-pointer ${
                  isSelected
                    ? 'bg-emerald-50 text-emerald-900 font-semibold'
                    : 'text-slate-700 hover:bg-slate-50 hover:text-emerald-800'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <span className="text-base">{lang.flag}</span>
                  <div>
                    <div className="leading-tight text-slate-900">{lang.nativeName}</div>
                    <div className="text-[10px] text-slate-400">{lang.name}</div>
                  </div>
                </div>
                {isSelected && <Check className="w-4 h-4 text-emerald-600" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
