
import { useState, useEffect } from 'react';
import { APISettings } from '../types/settings';

const STORAGE_KEY = 'bugfix_api_settings';

export function useSettings() {
  const [settings, setSettings] = useState<APISettings | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setSettings(JSON.parse(stored));
    }
  }, []);

  const updateSettings = (newSettings: APISettings) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings));
    setSettings(newSettings);
  };

  const clearSettings = () => {
    localStorage.removeItem(STORAGE_KEY);
    setSettings(null);
  };

  return {
    settings,
    updateSettings,
    clearSettings,
    isConfigured: !!settings
  };
}
