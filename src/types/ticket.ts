
export interface Ticket {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  reporter: string;
  assignee: string | null;
  created: string;
  updated: string;
  escalated?: boolean;
  current_attempt?: number;
  max_attempts?: number;
}

export interface PlannerAnalysis {
  ticket_id: string;
  bug_summary: string;
  affected_files: string[];
  error_type: string;
  using_fallback?: boolean;
  affectedFiles?: string[];  // For backward compatibility
  rootCause?: string;        // For backward compatibility
  suggestedApproach?: string; // For backward compatibility
}

export interface CodeDiff {
  filename: string;
  diff: string;
  linesAdded: number;
  linesRemoved: number;
}

export type TestStatus = 'pass' | 'fail';

export interface TestResult {
  name: string;
  status: TestStatus;
  duration: number;
  errorMessage?: string;
  output?: string;
}

export type UpdateType = 'jira' | 'github' | 'system';

export interface Update {
  timestamp: string;
  message: string;
  type: 'jira' | 'github' | 'system' | 'other';
  confidenceScore?: number;
}
