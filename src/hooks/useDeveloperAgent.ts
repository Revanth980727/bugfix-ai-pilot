
import { useState } from 'react';
import { CodeDiff } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

export function useDeveloperAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [diffs, setDiffs] = useState<CodeDiff[] | undefined>(undefined);
  const [attempt, setAttempt] = useState(1);
  const maxAttempts = 4;

  const simulateWork = (onComplete: () => void, mockDiffs: CodeDiff[]) => {
    setStatus('working');
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus('success');
          setDiffs(mockDiffs);
          onComplete();
          return 100;
        }
        return Math.min(prev + 2, 100);
      });
    }, 100);
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setDiffs(undefined);
    setAttempt(1);
  };

  return {
    status,
    progress,
    diffs,
    attempt,
    maxAttempts,
    simulateWork,
    reset
  };
}
