
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

  const simulateWork = (onComplete: () => void, mockResults: TestResult[], success: boolean = true) => {
    setStatus('working');
    
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
          
          onComplete();
          return 100;
        }
        return Math.min(prev + 5, 100);
      });
    }, 100);
  };

  const simulateFailure = (onComplete: () => void) => {
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
    
    simulateWork(onComplete, failedResults, false);
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
  };

  return {
    status,
    progress,
    testResults,
    summary,
    simulateWork,
    simulateFailure,
    determineTestCommand,
    reset
  };
}
