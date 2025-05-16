
import { useState } from 'react';
import { Update } from '../types/ticket';
import { AgentStatus } from './useDashboardState';

interface CommunicatorResult {
  prUrl?: string;
  jiraUrl?: string;
}

interface ValidationMetrics {
  totalPatches: number;
  validPatches: number;
  rejectedPatches: number;
  rejectionReasons: Record<string, number>;
}

export function useCommunicatorAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [updates, setUpdates] = useState<Update[] | undefined>(undefined);
  const [result, setResult] = useState<CommunicatorResult | undefined>(undefined);
  const [earlyEscalation, setEarlyEscalation] = useState(false);
  const [escalationReason, setEscalationReason] = useState<string | undefined>(undefined);
  const [confidenceScore, setConfidenceScore] = useState<number | undefined>(undefined);
  const [retryCount, setRetryCount] = useState(0);
  const [maxRetries, setMaxRetries] = useState(4);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [patchValidationResults, setPatchValidationResults] = useState<{
    isValid: boolean;
    rejectionReason?: string;
    validationMetrics?: ValidationMetrics;
    validationScore?: number;
    fileChecksums?: Record<string, string>; // Store file checksums
    patchesApplied?: number; // New field to track number of patches applied
    linesChanged?: { added: number; removed: number }; // Track lines changed
  } | undefined>(undefined);

  const simulateWork = (
    onComplete: () => void, 
    mockUpdates: Update[], 
    mockResult?: CommunicatorResult,
    options?: {
      isEarlyEscalation?: boolean;
      reason?: string;
      confidence?: number;
      retryCount?: number;
      maxRetries?: number;
      analytics?: any;
      patchValidation?: {
        isValid: boolean;
        rejectionReason?: string;
        validationMetrics?: ValidationMetrics;
        validationScore?: number;
        fileChecksums?: Record<string, string>;
        patchesApplied?: number;
        linesChanged?: { added: number; removed: number };
      };
    }
  ) => {
    setStatus('working');
    
    const {
      isEarlyEscalation,
      reason,
      confidence,
      retryCount: attemptCount,
      maxRetries: maxAttempts,
      analytics,
      patchValidation
    } = options || {};
    
    if (isEarlyEscalation) {
      setEarlyEscalation(true);
      setEscalationReason(reason);
    }
    
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
    
    if (attemptCount !== undefined) {
      setRetryCount(attemptCount);
    }
    
    if (maxAttempts !== undefined) {
      setMaxRetries(maxAttempts);
    }
    
    if (analytics) {
      setAnalyticsData(analytics);
    }
    
    if (patchValidation) {
      setPatchValidationResults(patchValidation);
    }
    
    // Add communication updates for retry attempts
    if (attemptCount && attemptCount > 0) {
      const retryUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: `Attempt ${attemptCount} of ${maxAttempts || 4}: ${isEarlyEscalation ? 'Escalated early' : 'Updating JIRA with latest fix details'}`,
        type: 'system',
        confidenceScore: confidence
      };
      
      mockUpdates = [retryUpdate, ...mockUpdates];
    }
    
    // Add patch validation update if applicable
    if (patchValidation) {
      const validationMessage = patchValidation.isValid 
        ? `✅ Patch validation passed - All file paths and diffs are valid ${patchValidation.validationScore ? `(Score: ${Math.round(patchValidation.validationScore)}%)` : ''}`
        : `❌ Patch validation failed: ${patchValidation.rejectionReason} ${patchValidation.validationScore ? `(Score: ${Math.round(patchValidation.validationScore)}%)` : ''}`;
      
      // Include patch application details if available
      const patchDetailsMessage = patchValidation.patchesApplied !== undefined
        ? ` (${patchValidation.patchesApplied} patches applied)`
        : '';
        
      // Include line changes if available
      const lineChangesMessage = patchValidation.linesChanged
        ? ` | +${patchValidation.linesChanged.added}/-${patchValidation.linesChanged.removed} lines`
        : '';
        
      const validationUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: validationMessage + patchDetailsMessage + lineChangesMessage,
        type: 'system',
        confidenceScore: confidence,
        metadata: {
          ...patchValidation,
          // If we have file checksums, include a truncated version for the update
          fileChecksums: patchValidation.fileChecksums 
            ? Object.fromEntries(
                Object.entries(patchValidation.fileChecksums)
                  .slice(0, 3) // Only show first 3 file checksums in the update
              ) 
            : undefined
        }
      };
      
      mockUpdates = [validationUpdate, ...mockUpdates];
      
      // If we have file checksums, add a detailed separate update
      if (patchValidation.fileChecksums && Object.keys(patchValidation.fileChecksums).length > 3) {
        const fileListUpdate: Update = {
          timestamp: new Date().toISOString(),
          message: `📋 Modified ${Object.keys(patchValidation.fileChecksums).length} files with patch`,
          type: 'system',
          metadata: {
            fileList: Object.keys(patchValidation.fileChecksums).slice(0, 10), // Show up to 10 filenames
            totalFiles: Object.keys(patchValidation.fileChecksums).length
          }
        };
        
        mockUpdates = [fileListUpdate, ...mockUpdates];
      }
    }
    
    // Add escalation update if applicable
    if (isEarlyEscalation || (attemptCount && maxAttempts && attemptCount >= maxAttempts)) {
      const escalationUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: isEarlyEscalation 
          ? `Early escalation: ${reason || 'Complex issue requiring human review'} ${confidence !== undefined ? `(Confidence Score: ${confidence}%)` : ''}`
          : `Escalated after ${maxAttempts} unsuccessful attempts. Assigning to human developer.`,
        type: 'jira',
        confidenceScore: confidence
      };
      
      mockUpdates = [escalationUpdate, ...mockUpdates];
    }
    
    // Add confidence score update if available
    if (confidence !== undefined && !isEarlyEscalation) {
      const confidenceLabel = confidence >= 80 ? "High" : (confidence >= 60 ? "Medium" : "Low");
      
      const confidenceUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: `Developer confidence score: ${confidence}% (${confidenceLabel})`,
        type: 'system',
        confidenceScore: confidence
      };
      
      mockUpdates = [confidenceUpdate, ...mockUpdates];
    }
    
    // Add validation metrics if available
    if (patchValidation?.validationMetrics) {
      const metrics = patchValidation.validationMetrics;
      const metricsUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: `Patch validation metrics: ${metrics.validPatches}/${metrics.totalPatches} patches valid`,
        type: 'system',
        metadata: {
          validationDetails: metrics
        }
      };
      
      mockUpdates = [metricsUpdate, ...mockUpdates];
    }
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus(isEarlyEscalation || (attemptCount && maxAttempts && attemptCount >= maxAttempts) ? 'escalated' : 'success');
          setUpdates(mockUpdates);
          if (mockResult && (!mockResult.prUrl || !mockResult.prUrl.includes('org/repo/pull') || mockResult.prUrl.match(/org\/repo\/pull\/\d+/))) {
            // Only set the result if it's a valid PR URL or doesn't contain placeholder values
            setResult(mockResult);
          } else if (mockResult) {
            // Handle case with placeholder PR URL - replace with more descriptive message
            const updatedResult = {
              ...mockResult,
              prUrl: mockResult.prUrl?.includes('org/repo/pull') ? undefined : mockResult.prUrl
            };
            setResult(updatedResult);
          }
          onComplete();
          return 100;
        }
        return Math.min(prev + 5, 100);
      });
    }, 100);
  };

  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setUpdates(undefined);
    setResult(undefined);
    setEarlyEscalation(false);
    setEscalationReason(undefined);
    setConfidenceScore(undefined);
    setRetryCount(0);
    setMaxRetries(4);
    setAnalyticsData(null);
    setPatchValidationResults(undefined);
  };

  return {
    status,
    progress,
    updates,
    prUrl: result?.prUrl,
    jiraUrl: result?.jiraUrl,
    earlyEscalation,
    escalationReason,
    confidenceScore,
    retryCount,
    maxRetries,
    analyticsData,
    patchValidationResults,
    simulateWork,
    reset
  };
}
