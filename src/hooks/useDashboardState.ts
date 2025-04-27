
import { useState, useCallback } from 'react';
import { Ticket, TestResult } from '../types/ticket';
import { toast } from '@/components/ui/sonner';
import { mockTicket, mockPlannerAnalysis, mockDiffs, mockTestResults, mockUpdates, mockTicketsList } from '../data/mockData';
import { usePlannerAgent } from './usePlannerAgent';
import { useDeveloperAgent } from './useDeveloperAgent';
import { useQAAgent } from './useQAAgent';
import { useCommunicatorAgent } from './useCommunicatorAgent';

export type AgentStatus = 'idle' | 'working' | 'success' | 'error' | 'waiting' | 'escalated';

export interface TicketListItem {
  id: string;
  title: string;
  status: string;
  stage: 'planning' | 'development' | 'qa' | 'pr-opened' | 'escalated' | 'completed';
  prUrl?: string;
  updatedAt: string;
  needsReview?: boolean;
}

export function useDashboardState() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  const [ticketsList, setTicketsList] = useState<TicketListItem[]>(mockTicketsList as TicketListItem[]);
  const [currentAttempt, setCurrentAttempt] = useState(1);
  const MAX_ATTEMPTS = 4; // Can be moved to env variable in a real implementation
  
  const planner = usePlannerAgent();
  const developer = useDeveloperAgent();
  const qa = useQAAgent();
  const communicator = useCommunicatorAgent();

  const resetAllAgents = () => {
    planner.reset();
    developer.reset();
    qa.reset();
    communicator.reset();
    setCurrentAttempt(1);
  };

  const handleTicketSubmit = (ticketId: string) => {
    setIsProcessing(true);
    toast.info(`Starting fix process for ticket ${ticketId}`);
    
    resetAllAgents();
    
    // Simulate fetching the ticket
    setTimeout(() => {
      setActiveTicket(mockTicket);
      simulateWorkflow();
      
      // Update the ticket list to show this ticket as in-progress
      setTicketsList(prev => 
        prev.map(ticket => 
          ticket.id === ticketId 
            ? { ...ticket, stage: 'planning' as const, status: 'in-progress' } 
            : ticket
        )
      );
    }, 1000);
  };

  const simulateWorkflow = () => {
    planner.simulateWork(
      () => startDeveloperPhase(1),
      mockPlannerAnalysis
    );
  };

  const startDeveloperPhase = (attempt: number) => {
    setCurrentAttempt(attempt);
    
    if (attempt > MAX_ATTEMPTS) {
      handleEscalation();
      return;
    }
    
    developer.simulateWork(
      () => startQaPhase(attempt),
      mockDiffs,
      attempt
    );
    
    // Update ticket status to show current attempt
    if (activeTicket) {
      setTicketsList(prev => 
        prev.map(ticket => 
          ticket.id === activeTicket.id 
            ? { 
                ...ticket, 
                stage: 'development' as const, 
                status: `attempt ${attempt}/${MAX_ATTEMPTS}` 
              } 
            : ticket
        )
      );
    }
  };
  
  const startQaPhase = (attempt: number) => {
    if (activeTicket) {
      setTicketsList(prev => 
        prev.map(ticket => 
          ticket.id === activeTicket.id 
            ? { ...ticket, stage: 'qa' as const, status: 'testing' } 
            : ticket
        )
      );
    }
    
    // For demo purposes, simulate QA passing on second attempt
    if (attempt === 2) {
      qa.simulateWork(
        () => startCommunicatorPhase(),
        mockTestResults
      );
    } else if (attempt < MAX_ATTEMPTS) {
      // Simulate QA failure and retry
      qa.simulateFailure(() => {
        toast.error(`QA tests failed for attempt ${attempt}. Retrying...`);
        // Wait a bit before starting next attempt
        setTimeout(() => startDeveloperPhase(attempt + 1), 1500);
      });
    } else {
      // Final attempt failed
      qa.simulateFailure(() => {
        handleEscalation();
      });
    }
  };
  
  const startCommunicatorPhase = () => {
    if (activeTicket) {
      setTicketsList(prev => 
        prev.map(ticket => 
          ticket.id === activeTicket.id 
            ? { ...ticket, stage: 'pr-opened' as const, status: 'finalizing' } 
            : ticket
        )
      );
    }
    
    communicator.simulateWork(
      () => {
        setIsProcessing(false);
        toast.success('Fix process completed successfully!', {
          description: 'PR created and JIRA updated.'
        });
        
        // Update the ticket list to show this ticket as completed
        if (activeTicket) {
          setTicketsList(prev => 
            prev.map(ticket => 
              ticket.id === activeTicket.id 
                ? { 
                    ...ticket, 
                    stage: 'pr-opened' as const, 
                    status: 'success',
                    prUrl: 'https://github.com/org/repo/pull/123' // Mock PR URL
                  } 
                : ticket
            )
          );
        }
      },
      mockUpdates
    );
  };
  
  const handleEscalation = () => {
    setIsProcessing(false);
    toast.error('Fix process has failed after maximum retries.', {
      description: 'Ticket has been escalated for human review.'
    });
    
    if (activeTicket) {
      setTicketsList(prev => 
        prev.map(ticket => 
          ticket.id === activeTicket.id 
            ? { 
                ...ticket, 
                stage: 'escalated' as const, 
                status: 'escalated',
                needsReview: true
              } 
            : ticket
        )
      );
    }
  };
  
  const fetchTickets = useCallback(() => {
    // In a real implementation, this would be an API call
    // For now, we're just using the mock data
    
    // Simulate API poll - in a real app, this would fetch fresh data from the backend
    console.log("Polling for ticket updates...");
    
    // We could simulate updates here by randomly changing the status of some tickets
    // But for now, we'll just leave it as is
  }, []);

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
    handleTicketSubmit,
    ticketsList,
    fetchTickets,
    currentAttempt,
    maxAttempts: MAX_ATTEMPTS
  };
}
