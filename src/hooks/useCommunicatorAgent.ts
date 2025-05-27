
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
      isTestMode?: boolean;
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
      patchValidation,
      isTestMode
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
    
    // Enhance communication updates for patch validation
    let enhancedMockUpdates = [...mockUpdates]; // Create a copy to avoid mutation
    
    // Add communication updates for retry attempts
    if (attemptCount && attemptCount > 0) {
      const retryUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: `Attempt ${attemptCount} of ${maxAttempts || 4}: ${isEarlyEscalation ? 'Escalated early' : 'Updating JIRA with latest fix details'}`,
        type: 'system',
        confidenceScore: confidence
      };
      
      enhancedMockUpdates = [retryUpdate, ...enhancedMockUpdates];
    }
    
    // Add test mode warning if applicable
    if (isTestMode) {
      const testModeUpdate: Update = {
        timestamp: new Date().toISOString(),
        message: `⚠️ Running in TEST_MODE - GitHub operations are simulated. Set TEST_MODE=False in .env for real GitHub interactions.`,
        type: 'system'
      };
      
      enhancedMockUpdates = [testModeUpdate, ...enhancedMockUpdates];
    }
    
    // Add detailed patch validation update if applicable
    if (patchValidation) {
      const patchDetailsMessage = patchValidation.patchesApplied !== undefined
        ? ` (${patchValidation.patchesApplied} files affected)`
        : '';
        
      const lineChangesMessage = patchValidation.linesChanged
        ? ` | +${patchValidation.linesChanged.added}/-${patchValidation.linesChanged.removed} lines`
        : '';
      
      // More detailed validation message with metrics
      let validationMessage: string;
      
      if (patchValidation.isValid) {
        validationMessage = `✅ Patch validation passed - All file paths found in diff${patchValidation.validationScore ? ` (Score: ${Math.round(patchValidation.validationScore)}%)` : ''}`;
      } else {
        validationMessage = `❌ Patch validation failed: ${patchValidation.rejectionReason || 'Unknown reason'}${patchValidation.validationScore ? ` (Score: ${Math.round(patchValidation.validationScore)}%)` : ''}`;
        
        // If we have metrics, add detailed failure reasons
        if (patchValidation.validationMetrics?.rejectionReasons) {
          const reasons = Object.entries(patchValidation.validationMetrics.rejectionReasons)
            .map(([reason, count]) => `${reason.replace('_', ' ')}: ${count} files`)
            .join(', ');
          
          if (reasons) {
            validationMessage += ` (${reasons})`;
          }
        }
      }
      
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
      
      enhancedMockUpdates = [validationUpdate, ...enhancedMockUpdates];
      
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
        
        enhancedMockUpdates = [fileListUpdate, ...enhancedMockUpdates];
      }
      
      // Add specific update for empty patch content or no file paths
      if (patchValidation.rejectionReason?.includes('empty') || 
          patchValidation.rejectionReason?.includes('No file paths')) {
        const emptyPatchUpdate: Update = {
          timestamp: new Date().toISOString(),
          message: `⚠️ Warning: ${patchValidation.rejectionReason}. No changes to commit.`,
          type: 'system',
          confidenceScore: confidence
        };
        
        enhancedMockUpdates = [emptyPatchUpdate, ...enhancedMockUpdates];
      }
      
      // Add GitHub configuration warnings if mock PR URL detected
      if (mockResult?.prUrl && 
          (mockResult.prUrl.includes('example-org') || 
           mockResult.prUrl.includes('org/repo') || 
           mockResult.prUrl.includes('999'))) {
        const mockPrUpdate: Update = {
          timestamp: new Date().toISOString(),
          message: `⚠️ Using mock PR URL due to ${isTestMode ? 'TEST_MODE' : 'invalid GitHub configuration'}: ${mockResult.prUrl}`,
          type: 'github'
        };
        
        enhancedMockUpdates = [mockPrUpdate, ...enhancedMockUpdates];
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
      
      enhancedMockUpdates = [escalationUpdate, ...enhancedMockUpdates];
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
      
      enhancedMockUpdates = [confidenceUpdate, ...enhancedMockUpdates];
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
      
      enhancedMockUpdates = [metricsUpdate, ...enhancedMockUpdates];
    }
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus(isEarlyEscalation || (attemptCount && maxAttempts && attemptCount >= maxAttempts) ? 'escalated' : 'success');
          setUpdates(enhancedMockUpdates);
          
          // Validate the PR URL before setting it
          let finalResult = { ...mockResult };
          if (mockResult?.prUrl) {
            const isPrMocked = mockResult.prUrl.includes('example-org/example-repo') || 
                              mockResult.prUrl.includes('org/repo/pull') ||
                              mockResult.prUrl.includes('/pull/999');
                              
            // Only set the PR URL if it's a valid URL or we're in test mode
            if (!isPrMocked || isTestMode) {
              finalResult.prUrl = mockResult.prUrl;
            } else {
              // In production mode, don't use mock URLs
              console.error(`Not using placeholder PR URL in production mode: ${mockResult.prUrl}`);
              finalResult.prUrl = undefined;
            }
          }
          
          setResult(finalResult);
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
