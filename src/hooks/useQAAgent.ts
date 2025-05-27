
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

  // Determine the appropriate test command based on project, but always default to pytest
  // since we know this project is Python-based and npm is not available in the containers
  const determineTestCommand = (projectType: string = 'python'): string => {
    // Always return pytest command for this project
    return 'python -m pytest';
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
