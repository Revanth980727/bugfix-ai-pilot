
import { useState } from 'react';
import { Ticket } from '../types/ticket';
import { toast } from '@/components/ui/sonner';
import { mockTicket, mockPlannerAnalysis, mockDiffs, mockTestResults, mockUpdates } from '../data/mockData';
import { usePlannerAgent } from './usePlannerAgent';
import { useDeveloperAgent } from './useDeveloperAgent';
import { useQAAgent } from './useQAAgent';
import { useCommunicatorAgent } from './useCommunicatorAgent';

export type AgentStatus = 'idle' | 'working' | 'success' | 'error' | 'waiting';

export function useDashboardState() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  
  const planner = usePlannerAgent();
  const developer = useDeveloperAgent();
  const qa = useQAAgent();
  const communicator = useCommunicatorAgent();

  const resetAllAgents = () => {
    planner.reset();
    developer.reset();
    qa.reset();
    communicator.reset();
  };

  const handleTicketSubmit = (ticketId: string) => {
    setIsProcessing(true);
    toast.info(`Starting fix process for ticket ${ticketId}`);
    
    resetAllAgents();
    
    // Simulate fetching the ticket
    setTimeout(() => {
      setActiveTicket(mockTicket);
      simulateWorkflow();
    }, 1000);
  };

  const simulateWorkflow = () => {
    planner.simulateWork(
      () => developer.simulateWork(
        () => qa.simulateWork(
          () => communicator.simulateWork(
            () => {
              setIsProcessing(false);
              toast.success('Fix process completed successfully!', {
                description: 'PR created and JIRA updated.'
              });
            },
            mockUpdates
          ),
          mockTestResults
        ),
        mockDiffs
      ),
      mockPlannerAnalysis
    );
  };

  return {
    isProcessing,
    activeTicket,
    plannerStatus: planner.status,
    developerStatus: developer.status,
    qaStatus: qa.status,
    communicatorStatus: communicator.status,
    plannerProgress: planner.progress,
    developerProgress: developer.progress,
    qaProgress: qa.progress,
    communicatorProgress: communicator.progress,
    plannerAnalysis: planner.analysis,
    diffs: developer.diffs,
    testResults: qa.testResults,
    updates: communicator.updates,
    handleTicketSubmit
  };
}
