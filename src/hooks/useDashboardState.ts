
import { useState } from 'react';
import { Ticket, PlannerAnalysis, CodeDiff, TestResult, Update } from '../types/ticket';
import { toast } from '@/components/ui/sonner';
import { mockTicket, mockPlannerAnalysis, mockDiffs, mockTestResults, mockUpdates } from '../data/mockData';

export type AgentStatus = 'idle' | 'working' | 'success' | 'error' | 'waiting';

export function useDashboardState() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  
  // Agent states
  const [plannerStatus, setPlannerStatus] = useState<AgentStatus>('idle');
  const [developerStatus, setDeveloperStatus] = useState<AgentStatus>('idle');
  const [qaStatus, setQaStatus] = useState<AgentStatus>('idle');
  const [communicatorStatus, setCommunicatorStatus] = useState<AgentStatus>('idle');
  
  const [plannerProgress, setPlannerProgress] = useState(0);
  const [developerProgress, setDeveloperProgress] = useState(0);
  const [qaProgress, setQaProgress] = useState(0);
  const [communicatorProgress, setCommunicatorProgress] = useState(0);
  
  // Analysis and results states
  const [plannerAnalysis, setPlannerAnalysis] = useState<PlannerAnalysis | undefined>(undefined);
  const [diffs, setDiffs] = useState<CodeDiff[] | undefined>(undefined);
  const [testResults, setTestResults] = useState<TestResult[] | undefined>(undefined);
  const [updates, setUpdates] = useState<Update[] | undefined>(undefined);

  const handleTicketSubmit = (ticketId: string) => {
    setIsProcessing(true);
    toast.info(`Starting fix process for ticket ${ticketId}`);
    
    // Reset all states
    setPlannerStatus('idle');
    setDeveloperStatus('idle');
    setQaStatus('idle');
    setCommunicatorStatus('idle');
    
    setPlannerProgress(0);
    setDeveloperProgress(0);
    setQaProgress(0);
    setCommunicatorProgress(0);
    
    setPlannerAnalysis(undefined);
    setDiffs(undefined);
    setTestResults(undefined);
    setUpdates(undefined);
    
    // Simulate fetching the ticket
    setTimeout(() => {
      setActiveTicket(mockTicket);
      simulateWorkflow();
    }, 1000);
  };

  const simulateWorkflow = () => {
    // Start planner agent
    setPlannerStatus('working');
    
    // Simulate planner progress
    const plannerInterval = setInterval(() => {
      setPlannerProgress(prev => {
        if (prev >= 100) {
          clearInterval(plannerInterval);
          setPlannerStatus('success');
          setPlannerAnalysis(mockPlannerAnalysis);
          simulateDeveloperWork();
          return 100;
        }
        return Math.min(prev + 1, 100);
      });
    }, 100);
  };

  const simulateDeveloperWork = () => {
    setDeveloperStatus('working');
    
    const developerInterval = setInterval(() => {
      setDeveloperProgress(prev => {
        if (prev >= 100) {
          clearInterval(developerInterval);
          setDeveloperStatus('success');
          setDiffs(mockDiffs);
          simulateQaWork();
          return 100;
        }
        return Math.min(prev + 2, 100);
      });
    }, 100);
  };

  const simulateQaWork = () => {
    setQaStatus('working');
    
    const qaInterval = setInterval(() => {
      setQaProgress(prev => {
        if (prev >= 100) {
          clearInterval(qaInterval);
          setQaStatus('success');
          setTestResults(mockTestResults);
          simulateCommunicatorWork();
          return 100;
        }
        return Math.min(prev + 5, 100);
      });
    }, 100);
  };

  const simulateCommunicatorWork = () => {
    setCommunicatorStatus('working');
    
    const commInterval = setInterval(() => {
      setCommunicatorProgress(prev => {
        if (prev >= 100) {
          clearInterval(commInterval);
          setCommunicatorStatus('success');
          setUpdates(mockUpdates);
          setIsProcessing(false);
          
          toast.success('Fix process completed successfully!', {
            description: 'PR created and JIRA updated.'
          });
          
          return 100;
        }
        return Math.min(prev + 5, 100);
      });
    }, 100);
  };

  return {
    isProcessing,
    activeTicket,
    plannerStatus,
    developerStatus,
    qaStatus,
    communicatorStatus,
    plannerProgress,
    developerProgress,
    qaProgress,
    communicatorProgress,
    plannerAnalysis,
    diffs,
    testResults,
    updates,
    handleTicketSubmit
  };
}

