
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
  const [patchAnalytics, setPatchAnalytics] = useState<any>(null);
  const maxAttempts = 4;

  /**
   * Simulate developer agent work
   */
  const simulateWork = (
    onComplete: () => void, 
    mockDiffs: CodeDiff[], 
    currentAttempt: number = 1,
    patchConfidence?: number,
    analytics?: any
  ) => {
    setStatus('working');
    setAttempt(currentAttempt);
    
    if (patchConfidence !== undefined) {
      setConfidenceScore(patchConfidence);
    }
    
    if (analytics) {
      setPatchAnalytics(analytics);
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

  /**
   * Simulate a failure in the developer agent
   */
  const simulateFailure = (reason?: string) => {
    setStatus('error');
    if (reason) {
      setEscalationReason(reason);
    }
  };
  
  /**
   * Simulate an early escalation due to low confidence or complexity
   */
  const simulateEarlyEscalation = (reason: string, confidence?: number) => {
    setStatus('escalated');
    setEarlyEscalation(true);
    setEscalationReason(reason);
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
  };

  /**
   * Reset the agent state
   */
  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setDiffs(undefined);
    setAttempt(1);
    setConfidenceScore(undefined);
    setEscalationReason(undefined);
    setEarlyEscalation(false);
    setPatchAnalytics(null);
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
    patchAnalytics,
    simulateWork,
    simulateFailure,
    simulateEarlyEscalation,
    reset
  };
}
