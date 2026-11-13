import React, { useState, useRef } from 'react';
import { Mic, MicOff, Loader2, Sparkles, X, Volume2, ArrowRight } from 'lucide-react';
import { transcribeAudio } from '../../services/api';
import { useLanguage } from '../../context/LanguageContext';
import { VoicePlayer } from './VoicePlayer';

interface VoiceQueryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onQuerySubmit?: (query: string) => void;
}

export const VoiceQueryModal: React.FC<VoiceQueryModalProps> = ({
  isOpen,
  onClose,
  onQuerySubmit,
}) => {
  const { language, currentLanguage, t } = useLanguage();
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  if (!isOpen) return null;

  // Sample farmer voice queries per language
  const sampleQueries: Record<string, string[]> = {
    te: [
      'ఈరోజు నా వరి పొలానికి నీరు పెట్టాలా?',
      'నేల తేమ 20% కంటే తక్కువగా ఉంటే ఏం చేయాలి?',
      'వర్షం వచ్చే అవకాశం ఉందా?',
    ],
    hi: [
      'क्या मुझे आज अपने गेहूं के खेत में सिंचाई करनी चाहिए?',
      'मिट्टी की नमी कम होने पर क्या करें?',
      'अगले 24 घंटों में बारिश का क्या पूर्वानुमान है?',
    ],
    ta: [
      'இன்று எனது நெல் வயலுக்கு நீர் பாய்ச்ச வேண்டுமா?',
      'மண் ஈரப்பதம் குறைவாக இருக்கும்போது என்ன செய்ய வேண்டும்?',
      'அடுத்த 24 மணிநேரத்தில் மழை பெய்யுமா?',
    ],
    kn: [
      'ಇಂದು ನನ್ನ ಭತ್ತದ ಗದ್ದೆಗೆ ನೀರುಣಿಸಬೇಕೆ?',
      'ಮಣ್ಣಿನ ತೇವಾಂಶ ಕಡಿಮೆಯಾದರೆ ಏನು ಮಾಡಬೇಕು?',
      'ಮುಂದಿನ 24 ಗಂಟೆಗಳಲ್ಲಿ ಮಳೆ ಮುನ್ಸೂಚನೆ ಏನು?',
    ],
    en: [
      'Should I irrigate my paddy field today?',
      'What should I do if soil moisture drops below 20%?',
      'Is rainfall forecast in the next 24 hours?',
    ],
  };

  const startRecording = async () => {
    setErrorMsg(null);
    setTranscribedText('');
    try {
      // First try browser native speech recognition if available for instant live feedback
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = currentLanguage.sarvamCode;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event: any) => {
          const speechResult = event.results[0][0].transcript;
          setTranscribedText(speechResult);
          setIsRecording(false);
        };

        recognition.onerror = (event: any) => {
          console.warn('Browser speech recognition notice:', event.error);
        };

        try {
          recognition.start();
        } catch (e) {
          console.warn('Recognition start error:', e);
        }
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        stream.getTracks().forEach((track) => track.stop());

        // Send to backend Sarvam STT if browser recognition didn't already capture it
        if (!transcribedText) {
          await processAudioWithSarvam(audioBlob);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err: any) {
      console.error('Microphone access failed:', err);
      setErrorMsg(
        'Could not access microphone. Please enable microphone permissions in your browser.'
      );
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const processAudioWithSarvam = async (blob: Blob) => {
    setIsProcessing(true);
    try {
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = async () => {
        const base64Audio = reader.result as string;
        try {
          const res = await transcribeAudio(base64Audio, currentLanguage.sarvamCode);
          if (res.transcript) {
            setTranscribedText(res.transcript);
          } else {
            setErrorMsg('Could not detect speech. Please speak closer to the microphone.');
          }
        } catch (e) {
          setErrorMsg('Voice transcription failed. You can also select a sample query below.');
        } finally {
          setIsProcessing(false);
        }
      };
    } catch (err) {
      setIsProcessing(false);
      setErrorMsg('Error processing voice audio.');
    }
  };

  const handleSelectSample = (sample: string) => {
    setTranscribedText(sample);
  };

  const handleSubmit = () => {
    if (transcribedText.trim()) {
      if (onQuerySubmit) {
        onQuerySubmit(transcribedText);
      }
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl max-w-lg w-full shadow-2xl border border-emerald-100 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-800 to-teal-800 p-6 text-white relative">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center text-emerald-300">
              <Mic className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold">
                {t('common.voiceAssistant', 'Farmer Voice Assistant')}
              </h3>
              <p className="text-xs text-emerald-200 mt-0.5">
                Powered by Sarvam AI Indic Speech &bull; {currentLanguage.nativeName} ({currentLanguage.code})
              </p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Recording Button */}
          <div className="flex flex-col items-center justify-center py-4">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isProcessing}
              className={`w-24 h-24 rounded-full flex items-center justify-center transition-all cursor-pointer shadow-lg ${
                isRecording
                  ? 'bg-rose-500 text-white ring-8 ring-rose-200 animate-pulse scale-105'
                  : 'bg-gradient-to-tr from-emerald-600 to-teal-500 text-white hover:scale-105 hover:shadow-emerald-500/25'
              }`}
            >
              {isProcessing ? (
                <Loader2 className="w-10 h-10 animate-spin" />
              ) : isRecording ? (
                <MicOff className="w-10 h-10" />
              ) : (
                <Mic className="w-10 h-10" />
              )}
            </button>

            <span className="text-sm font-semibold text-slate-700 mt-4">
              {isProcessing
                ? 'Processing speech with Sarvam AI...'
                : isRecording
                ? `${t('common.listening', 'Listening...')} (Click to Stop)`
                : `${t('common.speak', 'Click to Speak in')} ${currentLanguage.nativeName}`}
            </span>
            <span className="text-xs text-slate-400 mt-1">
              Supports Telugu, Hindi, Tamil, Kannada, and English
            </span>
          </div>

          {/* Transcribed Text Result Box */}
          {transcribedText && (
            <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-emerald-800 uppercase tracking-wider">
                <span>Recognized Query:</span>
                <VoicePlayer text={transcribedText} compact />
              </div>
              <p className="text-base font-semibold text-slate-800">{transcribedText}</p>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
              {errorMsg}
            </div>
          )}

          {/* Sample quick queries */}
          <div className="space-y-2">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Quick Farmer Queries ({currentLanguage.nativeName}):
            </div>
            <div className="space-y-1.5">
              {(sampleQueries[language] || sampleQueries.en).map((sq, i) => (
                <button
                  key={i}
                  onClick={() => handleSelectSample(sq)}
                  className="w-full text-left p-2.5 rounded-xl bg-slate-50 hover:bg-emerald-50 text-xs text-slate-700 hover:text-emerald-900 border border-slate-200 hover:border-emerald-300 transition-all flex items-center justify-between cursor-pointer group"
                >
                  <span>{sq}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-600 transition-transform group-hover:translate-x-1" />
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 cursor-pointer"
          >
            {t('common.close', 'Close')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!transcribedText.trim()}
            className="px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 disabled:pointer-events-none transition-all cursor-pointer shadow-sm flex items-center space-x-1.5"
          >
            <span>Ask Advisory</span>
            <Sparkles className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
