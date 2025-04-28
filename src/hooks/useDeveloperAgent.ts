
import { useState } from 'react';
import { CodeDiff } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

export function useDeveloperAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [diffs, setDiffs] = useState<CodeDiff[] | undefined>(undefined);
  const [attempt, setAttempt] = useState(1);
  const [confidenceScore, setConfidenceScore] = useState<number | undefined>(undefined);
  const [escalationReason, setEscalationReason] = useState<string | undefined>(undefined);
  const [earlyEscalation, setEarlyEscalation] = useState(false);
  const maxAttempts = 4;

  const simulateWork = (
    onComplete: () => void, 
    mockDiffs: CodeDiff[], 
    currentAttempt: number = 1,
    patchConfidence?: number
  ) => {
    setStatus('working');
    setAttempt(currentAttempt);
    if (patchConfidence !== undefined) {
      setConfidenceScore(patchConfidence);
    }
    
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

  const simulateFailure = (reason?: string) => {
    setStatus('error');
    if (reason) {
      setEscalationReason(reason);
    }
  };
  
  const simulateEarlyEscalation = (reason: string, confidence?: number) => {
    setStatus('escalated');
    setEarlyEscalation(true);
    setEscalationReason(reason);
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setDiffs(undefined);
    setAttempt(1);
    setConfidenceScore(undefined);
    setEscalationReason(undefined);
    setEarlyEscalation(false);
  };

  return {
    status,
    progress,
    diffs,
    attempt,
    maxAttempts,
    confidenceScore,
    escalationReason,
    earlyEscalation,
    simulateWork,
    simulateFailure,
    simulateEarlyEscalation,
    reset
  };
}
