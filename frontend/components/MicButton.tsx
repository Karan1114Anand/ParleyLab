'use client';

import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { Mic, MicOff, Square } from 'lucide-react';
import { useEffect } from 'react';

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

/**
 * MicButton — push-to-talk voice input.
 *
 * - Pulses red while recording.
 * - Streams interim transcript to the parent via onTranscript.
 * - Hidden gracefully if browser doesn't support Web Speech API.
 */
export function MicButton({ onTranscript, disabled }: Props) {
  const { transcript, isListening, isSupported, start, stop, resetTranscript } =
    useSpeechRecognition();

  // Stream transcript to parent in real time
  useEffect(() => {
    if (transcript) {
      onTranscript(transcript);
    }
  }, [transcript, onTranscript]);

  // Reset transcript when recording stops
  useEffect(() => {
    if (!isListening) {
      resetTranscript();
    }
  }, [isListening, resetTranscript]);

  if (!isSupported) return null;

  const handleClick = () => {
    if (isListening) {
      stop();
    } else {
      start();
    }
  };

  return (
    <button
      id="mic-button"
      type="button"
      onClick={handleClick}
      disabled={disabled}
      title={isListening ? 'Stop recording (click)' : 'Start voice input'}
      aria-label={isListening ? 'Stop recording' : 'Start voice recording'}
      className={`
        relative w-10 h-10 rounded-full flex items-center justify-center
        transition-all duration-200 shrink-0
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-transparent
        disabled:opacity-50 disabled:cursor-not-allowed
        ${isListening
          ? 'bg-red-500/20 border-2 border-red-500 text-red-400 mic-recording focus:ring-red-500'
          : 'bg-white/5 border border-white/10 text-[var(--text-muted)] hover:bg-white/10 hover:text-white hover:border-white/20 focus:ring-brand-500'
        }
      `}
    >
      {isListening ? (
        <Square className="w-3.5 h-3.5 fill-current" />
      ) : (
        <Mic className="w-4 h-4" />
      )}

      {/* Live indicator dot */}
      {isListening && (
        <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-[var(--bg-primary)] animate-pulse" />
      )}
    </button>
  );
}
