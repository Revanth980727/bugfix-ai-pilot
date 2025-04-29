
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
  const [retryCount, setRetryCount] = useState(0);
  const [maxRetries, setMaxRetries] = useState(4);

  const simulateWork = (
    onComplete: () => void, 
    mockUpdates: Update[], 
    mockResult?: CommunicatorResult,
    options?: {
      isEarlyEscalation?: boolean;
      reason?: string;
      confidence?: number;
      retryCount?: number;
      maxRetries?: number;
    }
  ) => {
    setStatus('working');
    
    const {
      isEarlyEscalation,
      reason,
      confidence,
      retryCount: attemptCount,
      maxRetries: maxAttempts
    } = options || {};
    
    if (isEarlyEscalation) {
      setEarlyEscalation(true);
      setEscalationReason(reason);
    }
    
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
    
    if (attemptCount !== undefined) {
      setRetryCount(attemptCount);
    }
    
    if (maxAttempts !== undefined) {
      setMaxRetries(maxAttempts);
    }
    
    // Add communication updates for retry attempts
    if (attemptCount && attemptCount > 0) {
      const retryUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: `Attempt ${attemptCount} of ${maxAttempts || 4}: ${isEarlyEscalation ? 'Escalated early' : 'Updating JIRA with latest fix details'}`,
        type: 'system',
        confidenceScore: confidence
      };
      
      mockUpdates = [retryUpdate, ...mockUpdates];
    }
    
    // Add escalation update if applicable
    if (isEarlyEscalation || (attemptCount && maxAttempts && attemptCount >= maxAttempts)) {
      const escalationUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: isEarlyEscalation 
          ? `Early escalation: ${reason || 'Complex issue requiring human review'}`
          : `Escalated after ${maxAttempts} unsuccessful attempts. Assigning to human developer.`,
        type: 'jira',
        confidenceScore: confidence
      };
      
      mockUpdates = [escalationUpdate, ...mockUpdates];
    }
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus(isEarlyEscalation || (attemptCount && maxAttempts && attemptCount >= maxAttempts) ? 'escalated' : 'success');
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
    setRetryCount(0);
    setMaxRetries(4);
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
    retryCount,
    maxRetries,
    simulateWork,
    reset
  };
}
