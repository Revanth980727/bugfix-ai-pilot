
import { useState, useCallback } from 'react';
import { Ticket } from '../types/ticket';
import { toast } from '@/components/ui/sonner';
import { mockTicket, mockPlannerAnalysis, mockDiffs, mockTestResults, mockUpdates, mockTicketsList } from '../data/mockData';
import { usePlannerAgent } from './usePlannerAgent';
import { useDeveloperAgent } from './useDeveloperAgent';
import { useQAAgent } from './useQAAgent';
import { useCommunicatorAgent } from './useCommunicatorAgent';

export type AgentStatus = 'idle' | 'working' | 'success' | 'error' | 'waiting';

export function useDashboardState() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  const [ticketsList, setTicketsList] = useState(mockTicketsList);
  
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
      
      // Update the ticket list to show this ticket as in-progress
      setTicketsList(prev => 
        prev.map(ticket => 
          ticket.id === ticketId 
            ? { ...ticket, stage: 'planning', status: 'in-progress' } 
            : ticket
        )
      );
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
              
              // Update the ticket list to show this ticket as completed
              if (activeTicket) {
                setTicketsList(prev => 
                  prev.map(ticket => 
                    ticket.id === activeTicket.id 
                      ? { ...ticket, stage: 'pr-opened', status: 'success' } 
                      : ticket
                  )
                );
              }
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
    fetchTickets
  };
}
