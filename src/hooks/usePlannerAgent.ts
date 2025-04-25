
import { useState } from 'react';
import { PlannerAnalysis } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

export function usePlannerAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [analysis, setAnalysis] = useState<PlannerAnalysis | undefined>(undefined);

  const simulateWork = (onComplete: () => void, mockAnalysis: PlannerAnalysis) => {
    setStatus('working');
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus('success');
          setAnalysis(mockAnalysis);
          onComplete();
          return 100;
        }
        return Math.min(prev + 1, 100);
      });
    }, 100);
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setAnalysis(undefined);
  };

  return {
    status,
    progress,
    analysis,
    simulateWork,
    reset
  };
}
