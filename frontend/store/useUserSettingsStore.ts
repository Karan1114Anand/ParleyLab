'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * Persisted user settings — country and profile name.
 *
 * Stored in localStorage so settings survive page reloads.
 * The selected country drives currency conversion, and the
 * user name is passed to the backend for personalized negotiation dialogue.
 */

export interface UserSettings {
  userName: string;
  countryCode: string;  // ISO 3166-1 alpha-2
  isConfigured: boolean;
}

interface UserSettingsStore extends UserSettings {
  setUserName: (name: string) => void;
  setCountryCode: (code: string) => void;
  markConfigured: () => void;
  reset: () => void;
}

const DEFAULT_SETTINGS: UserSettings = {
  userName: '',
  countryCode: 'US',
  isConfigured: false,
};

export const useUserSettingsStore = create<UserSettingsStore>()(
  persist(
    (set) => ({
      ...DEFAULT_SETTINGS,

      setUserName: (name) =>
        set({ userName: name }),

      setCountryCode: (code) =>
        set({ countryCode: code }),

      markConfigured: () =>
        set({ isConfigured: true }),

      reset: () =>
        set({ ...DEFAULT_SETTINGS }),
    }),
    {
      name: 'parleylab-user-settings',
    },
  ),
);
