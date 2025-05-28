
import { Ticket, PlannerAnalysis, CodeDiff, TestResult, Update } from '../types/ticket';

// Remove hardcoded mock data and create interfaces for real data
export interface AgentOutput {
  planner?: PlannerAnalysis;
  developer?: {
    ticket_id: string;
    patched_files: string[];
    patched_code: Record<string, string>;
    diffs: CodeDiff[];
    confidence_score: number;
    patch_mode: string;
  };
  qa?: {
    ticket_id: string;
    test_results: TestResult[];
    summary: {
      total: number;
      passed: number;
      failed: number;
      duration: number;
    };
    passed: boolean;
  };
}

// Function to fetch real ticket data from backend
export async function fetchTicketData(ticketId: string): Promise<AgentOutput | null> {
  try {
    const response = await fetch(`/api/tickets/${ticketId}`);
    if (response.ok) {
      return await response.json();
    }
    return null;
  } catch (error) {
    console.error('Error fetching ticket data:', error);
    return null;
  }
}

// Function to get current processing status
export async function getProcessingStatus(): Promise<any[]> {
  try {
    const response = await fetch('/api/tickets/status');
    if (response.ok) {
      return await response.json();
    }
    return [];
  } catch (error) {
    console.error('Error fetching processing status:', error);
    return [];
  }
}
