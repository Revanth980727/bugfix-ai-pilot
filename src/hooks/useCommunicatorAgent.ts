
import { useState } from 'react';
import { Update } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

interface CommunicatorResult {
  prUrl?: string;
  jiraUrl?: string;
}

export function useCommunicatorAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [updates, setUpdates] = useState<Update[] | undefined>(undefined);
  const [result, setResult] = useState<CommunicatorResult | undefined>(undefined);
  const [earlyEscalation, setEarlyEscalation] = useState(false);
  const [escalationReason, setEscalationReason] = useState<string | undefined>(undefined);
  const [confidenceScore, setConfidenceScore] = useState<number | undefined>(undefined);

  const simulateWork = (
    onComplete: () => void, 
    mockUpdates: Update[], 
    mockResult?: CommunicatorResult,
    isEarlyEscalation?: boolean,
    reason?: string,
    confidence?: number
  ) => {
    setStatus('working');
    
    if (isEarlyEscalation) {
      setEarlyEscalation(true);
      setEscalationReason(reason);
    }
    
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus('success');
          setUpdates(mockUpdates);
          if (mockResult) {
            setResult(mockResult);
          }
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
    setResult(undefined);
    setEarlyEscalation(false);
    setEscalationReason(undefined);
    setConfidenceScore(undefined);
  };

  return {
    status,
    progress,
    updates,
    prUrl: result?.prUrl,
    jiraUrl: result?.jiraUrl,
    earlyEscalation,
    escalationReason,
    confidenceScore,
    simulateWork,
    reset
  };
}
