
import { useState } from 'react';
import { Update } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

export function useCommunicatorAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [updates, setUpdates] = useState<Update[] | undefined>(undefined);

  const simulateWork = (onComplete: () => void, mockUpdates: Update[]) => {
    setStatus('working');
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus('success');
          setUpdates(mockUpdates);
          onComplete();
          return 100;
        }
        return Math.min(prev + 5, 100);
      });
    }, 100);
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setUpdates(undefined);
  };

  return {
    status,
    progress,
    updates,
    simulateWork,
    reset
  };
}
