import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  X,
  Send,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sparkles,
  Bot,
  User,
  Loader2,
  ChevronDown,
  RefreshCw,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { askAssistant, getAssistantGreeting } from '../../services/api';
import { playAudioFromBase64, stopCurrentAudio } from '../../utils/speech';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  audioBase64?: string | null;
  timestamp: string;
  fieldDetails?: string;
}

export const AIAssistantWidget: React.FC = () => {
  const { language, currentLanguage, t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [recognitionError, setRecognitionError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  // Auto-scroll to bottom of conversation
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen, isLoading]);

  // Global event listener to open assistant from anywhere
  useEffect(() => {
    const handleOpen = () => setIsOpen(true);
    window.addEventListener('open-agripulse-assistant', handleOpen);
    return () => window.removeEventListener('open-agripulse-assistant', handleOpen);
  }, []);

  // Load localized greeting and suggestions when language changes or first opened
  useEffect(() => {
    let isMounted = true;
    const fetchGreeting = async () => {
      try {
        const data = await getAssistantGreeting(language);
        if (isMounted) {
          setSuggestions(data.suggestions || []);
          // If no messages yet or language changed, set the localized greeting
          setMessages([
            {
              id: 'initial-greeting',
              sender: 'assistant',
              text: data.greeting,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
        }
      } catch (err) {
        console.warn('Could not fetch assistant greeting:', err);
      }
    };

    fetchGreeting();
    return () => {
      isMounted = false;
      stopCurrentAudio();
    };
  }, [language]);

  // Handle Play/Stop Audio for a specific message
  const handleToggleAudio = (messageId: string, audioBase64?: string | null) => {
    if (playingMessageId === messageId) {
      stopCurrentAudio();
      setPlayingMessageId(null);
      return;
    }

    if (!audioBase64) return;

    stopCurrentAudio();
    setPlayingMessageId(messageId);
    playAudioFromBase64(
      audioBase64,
      () => setPlayingMessageId(null),
      () => setPlayingMessageId(null)
    );
  };

  // Submit Query
  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || inputText).trim();
    if (!textToSend || isLoading) return;

    stopCurrentAudio();
    setPlayingMessageId(null);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsLoading(true);

    try {
      const response = await askAssistant(textToSend, language, null, true);

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: response.answer,
        audioBase64: response.audio_base64,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        fieldDetails: response.field_name
          ? `${response.field_name} (${response.crop_type})`
          : undefined,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      if (response.suggestions && response.suggestions.length > 0) {
        setSuggestions(response.suggestions);
      }

      // Auto-play speech if enabled and audio is available
      if (autoSpeak && response.audio_base64) {
        setPlayingMessageId(assistantMsg.id);
        playAudioFromBase64(
          response.audio_base64,
          () => setPlayingMessageId(null),
          () => setPlayingMessageId(null)
        );
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `assistant-error-${Date.now()}`,
        sender: 'assistant',
        text:
          language === 'te'
            ? 'క్షమించండి, మీ ప్రశ్నకు సమాధానం ఇవ్వడంలో సమస్య ఏర్పడింది. దయచేసి మళ్లీ ప్రయత్నించండి.'
            : language === 'hi'
            ? 'क्षमा करें, आपके प्रश्न का उत्तर देने में समस्या आई। कृपया पुनः प्रयास करें।'
            : language === 'ta'
            ? 'மன்னிக்கவும், உங்கள் கேள்விக்கு பதிலளிப்பதில் சிக்கல் ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.'
            : language === 'kn'
            ? 'ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರಿಸಲು ಸಮಸ್ಯೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.'
            : 'Sorry, I encountered an issue processing your request. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // Speech Recognition (Voice Input)
  const toggleRecording = () => {
    setRecognitionError(null);

    if (isRecording) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setRecognitionError('Speech recognition is not supported in this browser. Please use text chat.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = currentLanguage.sarvamCode; // e.g. 'te-IN', 'hi-IN', 'ta-IN', 'kn-IN', 'en-IN'
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsRecording(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((res: any) => res[0].transcript)
          .join('');
        setInputText(transcript);
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        setIsRecording(false);
        if (event.error !== 'no-speech') {
          setRecognitionError(`Voice input error (${event.error}). Please type your message.`);
        }
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.error('Failed to start speech recognition:', err);
      setIsRecording(false);
      setRecognitionError('Unable to access microphone.');
    }
  };

  return (
    <>
      {/* ── Floating Launcher Button (Bottom Right) ── */}
      {!isOpen && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center space-x-2">
          {/* Subtle Attention Tooltip */}
          <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 bg-slate-900/90 text-white text-xs font-semibold rounded-full shadow-lg backdrop-blur-xs border border-slate-700 animate-fade-in">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>
              {language === 'te'
                ? 'వ్యవసాయ AI సహాయకుడు'
                : language === 'hi'
                ? 'कृषि AI सहायक'
                : language === 'ta'
                ? 'வேளாண் AI உதவியாளர்'
                : language === 'kn'
                ? 'ಕೃಷಿ AI ಸಹಾಯಕ'
                : 'Ask AgriPulse AI'}
            </span>
          </div>

          <button
            onClick={() => setIsOpen(true)}
            className="group relative flex items-center justify-center w-14 h-14 rounded-full bg-gradient-to-tr from-emerald-700 via-emerald-600 to-teal-500 text-white shadow-xl hover:shadow-2xl hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
            title="Open AgriPulse Voice & Chat Assistant"
            aria-label="Open AI Assistant"
          >
            <span className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500 border-2 border-white"></span>
            </span>
            <Bot className="w-7 h-7 group-hover:rotate-6 transition-transform" />
          </button>
        </div>
      )}

      {/* ── Floating Chatbot Window (Bottom Right) ── */}
      {isOpen && (
        <div
          className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50 w-[360px] sm:w-[420px] max-w-[calc(100vw-32px)] h-[580px] max-h-[calc(100vh-100px)] bg-white rounded-3xl shadow-2xl border border-slate-200/90 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-6 duration-200"
          role="dialog"
          aria-label="AgriPulse AI Agricultural Voice & Chat Assistant"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-emerald-800 via-emerald-700 to-teal-700 text-white p-4 flex items-center justify-between shadow-md shrink-0">
            <div className="flex items-center space-x-3">
              <div className="relative w-10 h-10 rounded-2xl bg-white/15 backdrop-blur-xs flex items-center justify-center border border-white/20">
                <Bot className="w-6 h-6 text-emerald-200" />
                <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-400 rounded-full border-2 border-emerald-800"></span>
              </div>
              <div>
                <div className="flex items-center space-x-1.5">
                  <h3 className="font-bold text-sm tracking-tight">AgriPulse AI Assistant</h3>
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-white/20 text-emerald-100 border border-white/20">
                    {currentLanguage.nativeName}
                  </span>
                </div>
                <p className="text-[11px] text-emerald-200 font-medium">
                  Voice &amp; ML Irrigation Advisory
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-1">
              {/* Voice auto-play toggle */}
              <button
                type="button"
                onClick={() => setAutoSpeak(!autoSpeak)}
                title={autoSpeak ? 'Voice output enabled (click to mute)' : 'Voice output muted (click to enable)'}
                className={`p-2 rounded-xl transition-colors cursor-pointer ${
                  autoSpeak ? 'bg-white/20 text-white' : 'bg-transparent text-white/60 hover:text-white'
                }`}
              >
                {autoSpeak ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
              </button>

              {/* Close / Minimize */}
              <button
                type="button"
                onClick={() => {
                  stopCurrentAudio();
                  setIsOpen(false);
                }}
                className="p-2 rounded-xl hover:bg-white/20 text-white transition-colors cursor-pointer"
                title="Minimize Assistant"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-slate-50/50">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`flex items-start space-x-2 max-w-[88%] ${
                    msg.sender === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 text-xs ${
                      msg.sender === 'user'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-white border border-slate-200 text-emerald-700 shadow-2xs'
                    }`}
                  >
                    {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>

                  <div
                    className={`rounded-2xl p-3 text-xs leading-relaxed shadow-2xs ${
                      msg.sender === 'user'
                        ? 'bg-emerald-700 text-white rounded-tr-none'
                        : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.text}</p>

                    {/* Assistant metadata + Speech button */}
                    {msg.sender === 'assistant' && (
                      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400 gap-2">
                        <div className="flex items-center space-x-1.5 truncate">
                          <Sparkles className="w-3 h-3 text-emerald-600 shrink-0" />
                          <span className="truncate">Sarvam Indic + ML Telemetry</span>
                        </div>

                        {msg.audioBase64 && (
                          <button
                            type="button"
                            onClick={() => handleToggleAudio(msg.id, msg.audioBase64)}
                            className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-md font-semibold transition-colors cursor-pointer ${
                              playingMessageId === msg.id
                                ? 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-400 animate-pulse'
                                : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                            }`}
                            title={playingMessageId === msg.id ? 'Stop audio' : 'Listen in your language'}
                          >
                            {playingMessageId === msg.id ? (
                              <>
                                <VolumeX className="w-3 h-3" />
                                <span>Stop</span>
                              </>
                            ) : (
                              <>
                                <Volume2 className="w-3 h-3" />
                                <span>Listen</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <span className="text-[10px] text-slate-400 mt-1 px-9">
                  {msg.timestamp}
                </span>
              </div>
            ))}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex items-start space-x-2">
                <div className="w-7 h-7 rounded-xl bg-white border border-slate-200 text-emerald-700 flex items-center justify-center shrink-0">
                  <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none p-3 shadow-2xs">
                  <div className="flex items-center space-x-2 text-xs text-slate-500">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-600 animate-bounce"></span>
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-600 animate-bounce [animation-delay:0.2s]"></span>
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-600 animate-bounce [animation-delay:0.4s]"></span>
                    <span className="text-[11px] font-medium text-slate-400 ml-1">
                      {language === 'te'
                        ? 'నేల తేమ మరియు వాతావరణం విశ్లేషిస్తోంది...'
                        : language === 'hi'
                        ? 'मिट्टी की नमी और मौसम का विश्लेषण जारी है...'
                        : language === 'ta'
                        ? 'மண் ஈரம் மற்றும் வானிலை ஆய்வு செய்கிறது...'
                        : language === 'kn'
                        ? 'ಮಣ್ಣಿನ ತೇವಾಂಶ ಮತ್ತು ಹವಾಮಾನ ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ...'
                        : 'Analyzing soil & weather telemetry...'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Quick Suggestions Chips */}
            {suggestions.length > 0 && !isLoading && (
              <div className="pt-2 space-y-1.5">
                <div className="text-[11px] font-semibold text-slate-400 px-1">
                  {language === 'te'
                    ? 'సూచించిన ప్రశ్నలు:'
                    : language === 'hi'
                    ? 'सुझाए गए प्रश्न:'
                    : language === 'ta'
                    ? 'பரிந்துரைக்கப்பட்ட கேள்விகள்:'
                    : language === 'kn'
                    ? 'ಸೂಚಿಸಲಾದ ಪ್ರಶ್ನೆಗಳು:'
                    : 'Suggested questions:'}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSendMessage(s)}
                      className="text-left text-[11px] py-1 px-2.5 bg-white hover:bg-emerald-50 text-slate-700 hover:text-emerald-900 border border-slate-200 hover:border-emerald-300 rounded-xl transition-all shadow-2xs cursor-pointer"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Recording Status Banner */}
          {isRecording && (
            <div className="px-4 py-2 bg-rose-50 border-t border-rose-200 flex items-center justify-between text-xs text-rose-800 animate-pulse">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-600"></span>
                <span className="font-semibold">
                  {language === 'te'
                    ? 'వినబడుతోంది... మాట్లాడండి'
                    : language === 'hi'
                    ? 'सुन रहे हैं... बोलिए'
                    : language === 'ta'
                    ? 'கேட்கிறது... பேசுங்கள்'
                    : language === 'kn'
                    ? 'ಆಲಿಸಲಾಗುತ್ತಿದೆ... ಮಾತನಾಡಿ'
                    : 'Listening... Speak your question'}
                </span>
              </div>
              <button
                type="button"
                onClick={toggleRecording}
                className="text-rose-900 font-bold underline text-[11px] cursor-pointer"
              >
                Stop
              </button>
            </div>
          )}

          {recognitionError && (
            <div className="px-3 py-1.5 bg-amber-50 text-amber-800 text-[11px] border-t border-amber-200 flex items-center justify-between">
              <span>{recognitionError}</span>
              <button
                type="button"
                onClick={() => setRecognitionError(null)}
                className="text-amber-900 font-bold ml-2 cursor-pointer"
              >
                ✕
              </button>
            </div>
          )}

          {/* Input Footer */}
          <div className="p-3 bg-white border-t border-slate-200/90 shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center space-x-2"
            >
              {/* Microphone Voice Input Button */}
              <button
                type="button"
                onClick={toggleRecording}
                title={isRecording ? 'Stop listening' : 'Speak your question in your language'}
                className={`p-2.5 rounded-2xl transition-all cursor-pointer ${
                  isRecording
                    ? 'bg-rose-600 text-white ring-4 ring-rose-200 animate-pulse'
                    : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 hover:text-emerald-900 border border-emerald-200'
                }`}
              >
                {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>

              {/* Text Input */}
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={
                  language === 'te'
                    ? 'నీటిపారుదల లేదా వాతావరణం గురించి అడగండి...'
                    : language === 'hi'
                    ? 'सिंचाई या मौसम के बारे में पूछें...'
                    : language === 'ta'
                    ? 'நீர்ப்பாசனம் அல்லது வானிலை பற்றி கேளுங்கள்...'
                    : language === 'kn'
                    ? 'ನೀರಾವರಿ ಅಥವಾ ಹವಾಮಾನದ ಬಗ್ಗೆ ಕೇಳಿ...'
                    : 'Ask about irrigation, soil, or weather...'
                }
                disabled={isLoading}
                className="flex-1 py-2 px-3 text-xs bg-slate-50 border border-slate-200 rounded-2xl focus:outline-emerald-600 focus:bg-white text-slate-800 placeholder-slate-400"
              />

              {/* Send Button */}
              <button
                type="submit"
                disabled={!inputText.trim() || isLoading}
                className="p-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white rounded-2xl shadow-xs transition-colors cursor-pointer"
                title="Send query"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
};

export default AIAssistantWidget;
