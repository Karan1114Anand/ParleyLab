'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

interface SpeechHookResult {
  transcript: string;
  isListening: boolean;
  isSupported: boolean;
  start: () => void;
  stop: () => void;
  resetTranscript: () => void;
}

/**
 * useSpeechRecognition — wraps the browser Web Speech API.
 *
 * - Works in Chrome, Edge, and Safari.
 * - Returns isSupported=false on Firefox (mic button hides itself).
 * - Streams interim results into `transcript` in real time.
 * - The user can edit the transcript in the InputBox before sending.
 */
export function useSpeechRecognition(): SpeechHookResult {
  const [transcript, setTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSupported] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window;
  });

  const recognitionRef = useRef<any>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  const start = useCallback(() => {
    if (!isSupported) return;

    const SR: any =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    const r = new SR();
    r.continuous = true;
    r.interimResults = true;
    r.lang = 'en-US';
    r.maxAlternatives = 1;

    r.onresult = (e: any) => {
      const text = Array.from(e.results as SpeechRecognitionResultList)
        .map((item: any) => (item as any)[0].transcript)
        .join('');
      setTranscript(text);
    };

    r.onerror = (e: any) => {
      console.warn('SpeechRecognition error:', e.error);
      if (e.error !== 'no-speech') {
        setIsListening(false);
      }
    };

    r.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = r;

    try {
      r.start();
      setIsListening(true);
    } catch (err) {
      console.warn('SpeechRecognition start failed:', err);
    }
  }, [isSupported]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript('');
  }, []);

  return { transcript, isListening, isSupported, start, stop, resetTranscript };
}
