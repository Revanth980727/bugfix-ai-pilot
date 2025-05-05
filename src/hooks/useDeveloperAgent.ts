
import { useState, useEffect } from 'react';
import { CodeDiff } from '../types/ticket';
import { AgentStatus } from './useDashboardState';
import { extractGitHubSourceFromEnv, logGitHubSource, GitHubSource } from '../utils/developerSourceLogger';
import { getGitHubConfig } from '../services/githubService';

export function useDeveloperAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [diffs, setDiffs] = useState<CodeDiff[] | undefined>(undefined);
  const [attempt, setAttempt] = useState(1);
  const [confidenceScore, setConfidenceScore] = useState<number | undefined>(undefined);
  const [escalationReason, setEscalationReason] = useState<string | undefined>(undefined);
  const [earlyEscalation, setEarlyEscalation] = useState(false);
  const [patchAnalytics, setPatchAnalytics] = useState<any>(null);
  const [rawOpenAIResponse, setRawOpenAIResponse] = useState<string | null>(null);
  const [responseQuality, setResponseQuality] = useState<'good' | 'generic' | 'invalid' | undefined>(undefined);
  const [patchMode, setPatchMode] = useState<'intelligent' | 'line-by-line' | 'direct'>('line-by-line');
  const [gitHubSource, setGitHubSource] = useState<GitHubSource | null>(null);
  const maxAttempts = 4;

  // Get GitHub configuration on component mount
  useEffect(() => {
    const fetchGitHubConfig = async () => {
      try {
        const config = await getGitHubConfig();
        if (config) {
          setGitHubSource({
            repo_owner: config.repo_owner,
            repo_name: config.repo_name,
            branch: config.branch,
            default_branch: config.default_branch,
            patch_mode: config.patch_mode
          });
          setPatchMode(config.patch_mode);
        }
      } catch (error) {
        console.error('Error fetching GitHub config:', error);
      }
    };
    
    fetchGitHubConfig();
  }, []);

  /**
   * Simulate developer agent work
   */
  const simulateWork = (
    onComplete: () => void, 
    mockDiffs: CodeDiff[], 
    currentAttempt: number = 1,
    patchConfidence?: number,
    analytics?: any,
    options?: {
      responseQuality?: 'good' | 'generic' | 'invalid';
      rawResponse?: string;
      patchMode?: 'intelligent' | 'line-by-line' | 'direct';
    }
  ) => {
    setStatus('working');
    setAttempt(currentAttempt);
    
    if (patchConfidence !== undefined) {
      setConfidenceScore(patchConfidence);
    }
    
    if (analytics) {
      setPatchAnalytics(analytics);
    }
    
    if (options?.responseQuality) {
      setResponseQuality(options.responseQuality);
    }
    
    if (options?.rawResponse) {
      setRawOpenAIResponse(options.rawResponse);
    }
    
    if (options?.patchMode) {
      setPatchMode(options.patchMode);
    }

    // If GitHub source isn't set yet from config, try from env
    if (!gitHubSource) {
      const source = extractGitHubSourceFromEnv();
      setGitHubSource(source);
      logGitHubSource(source);
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
  const simulateFailure = (reason?: string, responseQuality?: 'good' | 'generic' | 'invalid') => {
    setStatus('error');
    if (reason) {
      setEscalationReason(reason);
    }
    if (responseQuality) {
      setResponseQuality(responseQuality);
    }
  };
  
  /**
   * Simulate an early escalation due to low confidence or complexity
   */
  const simulateEarlyEscalation = (
    reason: string, 
    confidence?: number, 
    options?: {
      responseQuality?: 'good' | 'generic' | 'invalid';
      rawResponse?: string;
    }
  ) => {
    setStatus('escalated');
    setEarlyEscalation(true);
    setEscalationReason(reason);
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
    if (options?.responseQuality) {
      setResponseQuality(options.responseQuality);
    }
    if (options?.rawResponse) {
      setRawOpenAIResponse(options.rawResponse);
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
    setRawOpenAIResponse(null);
    setResponseQuality(undefined);
    setGitHubSource(null);
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
    rawOpenAIResponse,
    responseQuality,
    patchMode,
    gitHubSource,
    simulateWork,
    simulateFailure,
    simulateEarlyEscalation,
    reset
  };
}
