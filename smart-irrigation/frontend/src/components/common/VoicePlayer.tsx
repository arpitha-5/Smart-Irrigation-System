import React, { useState, useEffect } from 'react';
import { Volume2, VolumeX, Loader2, Sparkles } from 'lucide-react';
import { synthesizeSpeech } from '../../services/api';
import { playAudioFromBase64, speakWithBrowserSynthesis, stopCurrentAudio } from '../../utils/speech';
import { useLanguage } from '../../context/LanguageContext';

interface VoicePlayerProps {
  text: string;
  languageCode?: string;
  label?: string;
  compact?: boolean;
  className?: string;
  title?: string;
}

export const VoicePlayer: React.FC<VoicePlayerProps> = ({
  text,
  languageCode,
  label,
  compact = false,
  className = '',
  title,
}) => {
  const { language, t } = useLanguage();
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const activeLang = languageCode || language;

  // Cleanup when component unmounts
  useEffect(() => {
    return () => {
      if (isPlaying) {
        stopCurrentAudio();
      }
    };
  }, [isPlaying]);

  const handleTogglePlay = async (e: React.MouseEvent) => {
    e.stopPropagation();

    if (isPlaying) {
      stopCurrentAudio();
      setIsPlaying(false);
      return;
    }

    if (!text || !text.trim()) return;

    try {
      setIsLoading(true);

      // Attempt Sarvam TTS via backend API
      const res = await synthesizeSpeech(text, activeLang);

      if (res && res.audio_base64 && !res.fallback) {
        // High quality Sarvam Bulbul Indic TTS
        setIsLoading(false);
        setIsPlaying(true);
        playAudioFromBase64(
          res.audio_base64,
          () => setIsPlaying(false),
          () => {
            // If base64 decoding or audio element playback failed, fall back
            speakWithBrowserSynthesis(text, activeLang, () => setIsPlaying(false));
          }
        );
      } else {
        // Graceful client fallback using Web Speech API
        setIsLoading(false);
        setIsPlaying(true);
        speakWithBrowserSynthesis(
          text,
          activeLang,
          () => setIsPlaying(false),
          () => setIsPlaying(false)
        );
      }
    } catch (err) {
      console.warn('Sarvam TTS backend error, falling back to browser synthesis:', err);
      setIsLoading(false);
      setIsPlaying(true);
      speakWithBrowserSynthesis(
        text,
        activeLang,
        () => setIsPlaying(false),
        () => setIsPlaying(false)
      );
    }
  };

  if (compact) {
    return (
      <button
        type="button"
        onClick={handleTogglePlay}
        disabled={isLoading}
        title={title || t('common.listen', 'Listen in selected language')}
        className={`p-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 hover:bg-emerald-100 transition-all cursor-pointer ${
          isPlaying ? 'bg-emerald-200 text-emerald-950 ring-2 ring-emerald-400' : 'bg-emerald-50'
        } ${className}`}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
        ) : isPlaying ? (
          <VolumeX className="w-4 h-4 animate-pulse text-emerald-900" />
        ) : (
          <Volume2 className="w-4 h-4" />
        )}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleTogglePlay}
      disabled={isLoading}
      title={title || t('recommendations.listenAdvice', 'Listen to Advisory in Your Language')}
      className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer border ${
        isPlaying
          ? 'bg-rose-50 border-rose-200 text-rose-800 hover:bg-rose-100 ring-2 ring-rose-300'
          : 'bg-emerald-600 border-emerald-700 text-white hover:bg-emerald-700 hover:shadow-md'
      } ${className}`}
    >
      {isLoading ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>{t('common.loading', 'Loading voice...')}</span>
        </>
      ) : isPlaying ? (
        <>
          <VolumeX className="w-3.5 h-3.5 text-rose-700" />
          <span>{t('common.stop', 'Stop Audio')}</span>
          <span className="flex space-x-0.5 items-center ml-1">
            <span className="w-1 h-3 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
            <span className="w-1 h-4 bg-rose-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
            <span className="w-1 h-2 bg-rose-500 rounded-full animate-bounce" />
          </span>
        </>
      ) : (
        <>
          <Volume2 className="w-3.5 h-3.5" />
          <span>{label || t('recommendations.listenAdvice', 'Listen to Advice')}</span>
          <Sparkles className="w-3 h-3 text-emerald-200" />
        </>
      )}
    </button>
  );
};
