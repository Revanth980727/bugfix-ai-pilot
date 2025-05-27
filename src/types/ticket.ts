
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
  escalation_reason?: string;
  confidence_score?: number;
  retry_history?: Array<{
    result: 'success' | 'failure';
    qa_message?: string;
  }>;
  early_escalation?: boolean;
  code_context?: { [filePath: string]: string }; 
  github_source?: {
    repo_owner?: string;
    repo_name?: string;
    branch?: string;
    default_branch?: string;
    patch_mode?: string;
  };
}

export interface AffectedFile {
  file: string;
  valid: boolean;
  reason?: string;
  content?: string;
}

export interface PlannerAnalysis {
  ticket_id: string;
  bug_summary: string;
  affected_files: string[] | AffectedFile[];
  error_type: string;
  using_fallback?: boolean;
  affectedFiles?: string[];
  rootCause?: string;
  suggestedApproach?: string;
  code_context?: { [filePath: string]: string };
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

// Detailed metadata type definition for Update interface
export interface UpdateMetadata {
  fileList?: string[];
  totalFiles?: number;
  fileChecksums?: Record<string, string>;
  validationDetails?: {
    totalPatches?: number;
    validPatches?: number;
    rejectedPatches?: number;
    rejectionReasons?: Record<string, number>;
  };
  [key: string]: any; // Allow for other properties
}

export interface Update {
  timestamp: string;
  message: string;
  type: UpdateType;
  confidenceScore?: number;
  metadata?: UpdateMetadata;
  github_source?: {
    repo_owner?: string;
    repo_name?: string;
    branch?: string;
    patch_mode?: string;
  };
}

export interface GitHubConfig {
  repo_owner: string;
  repo_name: string;
  default_branch: string;
  branch: string;
  patch_mode: 'intelligent' | 'line-by-line' | 'direct';
  preserve_branch_case?: boolean;
  include_test_files?: boolean;
}
