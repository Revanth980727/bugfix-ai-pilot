
import { useState } from 'react';
import { TestResult } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

export function useQAAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [testResults, setTestResults] = useState<TestResult[] | undefined>(undefined);
  const [summary, setSummary] = useState<{ 
    total: number;
    passed: number;
    failed: number;
    duration: number;
  } | undefined>(undefined);
  // Track which orchestrator is currently running tests
  const [activeOrchestrator, setActiveOrchestrator] = useState<string | null>(null);

  const simulateWork = (onComplete: () => void, mockResults: TestResult[], success: boolean = true, orchestratorId: string = 'default') => {
    // If another orchestrator is already running tests, don't start again
    if (activeOrchestrator && activeOrchestrator !== orchestratorId && status === 'working') {
      console.log(`QA tests already in progress by orchestrator: ${activeOrchestrator}, skipping request from: ${orchestratorId}`);
      return;
    }
    
    setStatus('working');
    setActiveOrchestrator(orchestratorId);
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus(success ? 'success' : 'error');
          setTestResults(mockResults);
          
          // Calculate summary stats
          const passed = mockResults.filter(r => r.status === 'pass').length;
          const failed = mockResults.filter(r => r.status === 'fail').length;
          const totalTime = mockResults.reduce((sum, test) => sum + (test.duration || 0), 0);
          
          setSummary({
            total: mockResults.length,
            passed,
            failed,
            duration: totalTime
          });
          
          // Clear active orchestrator
          setActiveOrchestrator(null);
          onComplete();
          return 100;
        }
        return Math.min(prev + 5, 100);
      });
    }, 100);
  };

  const simulateFailure = (onComplete: () => void, orchestratorId: string = 'default') => {
    const failedResults: TestResult[] = [
      {
        name: 'Integration test',
        status: 'fail',
        duration: 423,
        errorMessage: 'Expected result to be equal to expected value'
      },
      {
        name: 'Unit test',
        status: 'fail',
        duration: 117,
        errorMessage: 'Cannot read property of undefined'
      }
    ];
    
    simulateWork(onComplete, failedResults, false, orchestratorId);
  };

  // Add a method to determine the appropriate test command based on project
  const determineTestCommand = (projectType: string = 'python'): string => {
    switch (projectType.toLowerCase()) {
      case 'javascript':
      case 'js':
      case 'node':
        return 'npm test';
      case 'python':
      case 'py':
        return 'python -m pytest';
      default:
        return 'python -m pytest'; // Default to Python test command
    }
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setTestResults(undefined);
    setSummary(undefined);
    setActiveOrchestrator(null);
  };

  return {
    status,
    progress,
    testResults,
    summary,
    activeOrchestrator,
    simulateWork,
    simulateFailure,
    determineTestCommand,
    reset
  };
}
