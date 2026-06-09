'use client';

import { useEffect, useState } from 'react';

/**
 * useTypewriter — animates a string character by character.
 * Returns the currently visible portion and a boolean `done`.
 */
export function useTypewriter(
  text: string,
  speed = 18,
  startDelay = 400
): { visible: string; done: boolean } {
  const [visible, setVisible] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    setVisible('');
    setDone(false);
    let i = 0;
    const start = setTimeout(() => {
      const timer = setInterval(() => {
        i++;
        setVisible(text.slice(0, i));
        if (i >= text.length) {
          clearInterval(timer);
          setDone(true);
        }
      }, speed);
      return () => clearInterval(timer);
    }, startDelay);
    return () => clearTimeout(start);
  }, [text, speed, startDelay]);

  return { visible, done };
}
