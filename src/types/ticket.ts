
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
}

export interface PlannerAnalysis {
  affectedFiles: string[];
  rootCause: string;
  suggestedApproach: string;
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
}

export type UpdateType = 'jira' | 'github' | 'system';

export interface Update {
  timestamp: string;
  message: string;
  type: UpdateType;
}

