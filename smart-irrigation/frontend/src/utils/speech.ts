/**
 * Audio and speech synthesis utilities supporting Sarvam AI output and browser Web Speech fallback.
 */

let currentAudio: HTMLAudioElement | null = null;

export const LANGUAGE_SPEECH_CODES: Record<string, string> = {
  en: 'en-IN',
  te: 'te-IN',
  hi: 'hi-IN',
  ta: 'ta-IN',
  kn: 'kn-IN',
};

export function stopCurrentAudio(): void {
  if (currentAudio) {
    try {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    } catch (e) {
      console.warn('Error pausing audio:', e);
    }
    currentAudio = null;
  }
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
}

export function playAudioFromBase64(
  base64Data: string,
  onEnded?: () => void,
  onError?: (err: any) => void
): HTMLAudioElement {
  stopCurrentAudio();

  // Strip data URI prefix if present
  const cleanB64 = base64Data.includes(',') ? base64Data.split(',')[1] : base64Data;
  const audioSrc = `data:audio/wav;base64,${cleanB64}`;

  const audio = new Audio(audioSrc);
  currentAudio = audio;

  audio.onended = () => {
    if (currentAudio === audio) {
      currentAudio = null;
    }
    if (onEnded) onEnded();
  };

  audio.onerror = (e) => {
    console.error('Audio playback error:', e);
    if (currentAudio === audio) {
      currentAudio = null;
    }
    if (onError) onError(e);
  };

  audio.play().catch((err) => {
    console.error('Failed to start audio playback:', err);
    if (onError) onError(err);
  });

  return audio;
}

export function speakWithBrowserSynthesis(
  text: string,
  langCode: string,
  onEnded?: () => void,
  onError?: (err: any) => void
): boolean {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    if (onError) onError(new Error('Browser speech synthesis not supported'));
    return false;
  }

  stopCurrentAudio();

  const targetLang = LANGUAGE_SPEECH_CODES[langCode] || langCode || 'en-IN';
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = targetLang;
  utterance.rate = 0.95; // slightly slower for clearer comprehension for farmers

  // Try to find a matching voice if possible
  const voices = window.speechSynthesis.getVoices();
  const matchedVoice = voices.find((v) => v.lang.toLowerCase().startsWith(langCode.toLowerCase()));
  if (matchedVoice) {
    utterance.voice = matchedVoice;
  }

  utterance.onend = () => {
    if (onEnded) onEnded();
  };

  utterance.onerror = (e) => {
    console.warn('Speech synthesis error:', e);
    if (onError) onError(e);
  };

  window.speechSynthesis.speak(utterance);
  return true;
}
