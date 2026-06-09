'use client';

import { MicButton } from '@/components/MicButton';
import { Send } from 'lucide-react';
import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

interface Props {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  accentColor?: string;
}

/**
 * Premium InputBox — auto-growing textarea with:
 * - Submit on Enter (Shift+Enter = newline)
 * - Animated focus ring in the scenario accent colour
 * - Character count indicator near the limit
 * - Disabled state with distinct visual treatment
 * - Voice transcript integration
 * - Send button with loading pulse animation while waiting
 */
export function InputBox({ onSubmit, disabled, placeholder, accentColor = '#6470f3' }: Props) {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus the textarea when it becomes enabled (opponent finished responding)
  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  const resize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const handleSubmit = useCallback(() => {
    const msg = value.trim();
    if (!msg || disabled) return;
    onSubmit(msg);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, disabled, onSubmit]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    resize();
  };

  const handleTranscript = useCallback((text: string) => {
    setValue(text);
    setTimeout(resize, 0);
  }, []);

  const canSubmit = value.trim().length > 0 && !disabled;
  const charCount = value.length;
  const nearLimit = charCount > 1600;

  const ringStyle = focused && !disabled
    ? { boxShadow: `0 0 0 1px ${accentColor}50, 0 4px 24px ${accentColor}10`, borderColor: `${accentColor}40` }
    : {};

  return (
    <div
      className="relative"
      style={{ transition: 'all 0.2s ease' }}
    >
      {/* Disabled overlay hint */}
      {disabled && (
        <div
          className="absolute -top-8 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[10px] text-white/40
            bg-white/[0.04] border border-white/[0.06] whitespace-nowrap animate-fade-up"
        >
          Waiting for response…
        </div>
      )}

      <div
        className={`
          relative flex items-end gap-2 rounded-2xl px-4 py-3
          bg-white/[0.04] border transition-all duration-300
          ${disabled ? 'opacity-60 border-white/[0.05]' : 'border-white/[0.08]'}
        `}
        style={ringStyle}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          id="negotiation-input"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          placeholder={
            disabled
              ? 'Waiting for the opponent to respond…'
              : (placeholder ?? 'State your position… (Enter to send, Shift+Enter for newline)')
          }
          rows={1}
          style={{ resize: 'none', minHeight: '40px', maxHeight: '160px' }}
          className="
            flex-1 bg-transparent text-sm text-white
            placeholder:text-white/25 focus:outline-none
            leading-relaxed py-0.5 scrollbar-hide
            disabled:cursor-not-allowed disabled:text-white/30
          "
        />

        {/* Right-side controls */}
        <div className="flex items-center gap-2 shrink-0 pb-0.5">
          {/* Char counter — only near limit */}
          {nearLimit && (
            <span className={`text-[10px] ${charCount > 1900 ? 'text-red-400' : 'text-white/30'}`}>
              {2000 - charCount}
            </span>
          )}

          {/* Mic */}
          <MicButton onTranscript={handleTranscript} disabled={disabled} />

          {/* Send */}
          <button
            id="send-button"
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            aria-label="Send message"
            style={canSubmit ? {
              background: `linear-gradient(135deg, ${accentColor}, #8b5cf6)`,
              boxShadow: `0 4px 16px ${accentColor}40`,
            } : {}}
            className="
              relative w-10 h-10 rounded-xl flex items-center justify-center shrink-0
              transition-all duration-200
              disabled:opacity-30 disabled:cursor-not-allowed
              enabled:hover:-translate-y-0.5 enabled:active:translate-y-0
              bg-white/[0.06] border border-white/[0.08]
            "
          >
            {disabled ? (
              /* Pulse rings while waiting */
              <span className="relative flex items-center justify-center">
                <span
                  className="absolute w-5 h-5 rounded-full border border-white/20 animate-ping"
                  style={{ animationDuration: '1.5s' }}
                />
                <Send className="w-4 h-4 text-white/30" />
              </span>
            ) : (
              <Send className="w-4 h-4 text-white" />
            )}
          </button>
        </div>
      </div>

      {/* Hint line */}
      {!disabled && value.length === 0 && (
        <p className="text-[10px] text-white/15 text-center mt-1.5">
          Enter to send · Shift+Enter for new line
        </p>
      )}
    </div>
  );
}
