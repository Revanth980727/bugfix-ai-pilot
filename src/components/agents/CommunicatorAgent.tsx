
import React from 'react';
import { AgentCard } from './AgentCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { GitPullRequest, MessageSquare, Github, AlertTriangle, Info, RefreshCcw, CheckCircle, XCircle, FileCode } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/components/ui/use-toast';
import { AgentStatus } from '@/hooks/useDashboardState';
import { Update } from '@/types/ticket';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface ValidationMetrics {
  totalPatches?: number;
  validPatches?: number;
  rejectedPatches?: number;
  rejectionReasons?: Record<string, number>;
}

interface CommunicatorAgentProps {
  status: AgentStatus;
  progress?: number;
  updates?: Update[];
  prUrl?: string;
  jiraUrl?: string;
  earlyEscalation?: boolean;
  escalationReason?: string;
  confidenceScore?: number;
  retryCount?: number;
  maxRetries?: number;
  patchValidationResults?: {
    isValid: boolean;
    rejectionReason?: string;
    validationMetrics?: ValidationMetrics;
    fileChecksums?: Record<string, string>;
    validationScore?: number;
  };
}

// Define interface for metadata types to help with TypeScript checking
interface FileListMetadata {
  fileList: string[];
  totalFiles: number;
}

interface FileChecksumsMetadata {
  fileChecksums: Record<string, string>;
}

export function CommunicatorAgent({ 
  status, 
  progress, 
  updates, 
  prUrl, 
  jiraUrl,
  earlyEscalation,
  escalationReason,
  confidenceScore,
  retryCount = 0,
  maxRetries = 4,
  patchValidationResults
}: CommunicatorAgentProps) {
  const { toast } = useToast();
  
  // Helper function to check if metadata has fileList property
  const hasFileList = (metadata: any): metadata is FileListMetadata => {
    return metadata && 
           typeof metadata === 'object' && 
           'fileList' in metadata && 
           Array.isArray(metadata.fileList) &&
           'totalFiles' in metadata &&
           typeof metadata.totalFiles === 'number';
  };
  
  // Helper function to check if metadata has fileChecksums property
  const hasFileChecksums = (metadata: any): metadata is FileChecksumsMetadata => {
    return metadata && 
           typeof metadata === 'object' && 
           'fileChecksums' in metadata &&
           typeof metadata.fileChecksums === 'object';
  };
  
  const handleButtonClick = (url: string, type: string) => {
    if (url) {
      window.open(url, '_blank');
    } else {
      toast({
        title: `No ${type} URL available`,
        description: `The ${type} URL is not available for this ticket.`,
        variant: "destructive",
      });
    }
  };

  const isEscalated = earlyEscalation || (retryCount >= maxRetries);
  
  // Helper function to determine confidence badge color
  const getConfidenceBadgeVariant = (score?: number) => {
    if (score === undefined) return "outline";
    if (score >= 80) return "success";
    if (score >= 60) return "default";
    return "destructive";
  };
  
  // Helper function to get a descriptive label for the confidence score
  const getConfidenceLabel = (score?: number) => {
    if (score === undefined) return "Unknown";
    if (score >= 80) return "High";
    if (score >= 60) return "Medium";
    return "Low";
  };

  // Get modified file count from validation results
  const modifiedFileCount = patchValidationResults?.fileChecksums 
    ? Object.keys(patchValidationResults.fileChecksums).length
    : 0;

  return (
    <AgentCard title="Communicator" type="communicator" status={status} progress={progress}>
      {retryCount > 0 && maxRetries > 0 && (
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RefreshCcw className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Attempt {retryCount}/{maxRetries}</span>
          </div>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Progress 
                  value={(retryCount / maxRetries) * 100} 
                  className={`h-2 w-24 ${retryCount >= maxRetries ? "bg-red-200" : ""}`}
                />
              </TooltipTrigger>
              <TooltipContent>
                <p>Retry progress: {retryCount} of {maxRetries} attempts used</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}
      
      {confidenceScore !== undefined && (
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Confidence:</span>
          <Badge variant={getConfidenceBadgeVariant(confidenceScore)}>
            {getConfidenceLabel(confidenceScore)} ({confidenceScore}%)
          </Badge>
        </div>
      )}
      
      {patchValidationResults && (
        <div className={`mb-3 p-2 border ${patchValidationResults.isValid ? 'border-green-200 bg-green-50 dark:bg-green-950/30 dark:border-green-900' : 'border-red-200 bg-red-50 dark:bg-red-950/30 dark:border-red-900'} rounded-md`}>
          <div className="flex items-start gap-2">
            {patchValidationResults.isValid ? (
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
            ) : (
              <XCircle className="h-5 w-5 text-red-500 mt-0.5" />
            )}
            <div className="text-sm">
              <p className={`font-medium ${patchValidationResults.isValid ? 'text-green-800 dark:text-green-300' : 'text-red-800 dark:text-red-300'}`}>
                {patchValidationResults.isValid ? 'Patch Validation Passed' : 'Patch Validation Failed'}
              </p>
              {!patchValidationResults.isValid && patchValidationResults.rejectionReason && (
                <p className="text-red-700 dark:text-red-400">
                  {patchValidationResults.rejectionReason}
                </p>
              )}
              {patchValidationResults.validationMetrics && (
                <p className="text-xs mt-1">
                  {patchValidationResults.validationMetrics.validPatches || 0}/{patchValidationResults.validationMetrics.totalPatches || 0} patches valid
                </p>
              )}
            </div>
          </div>
          
          {/* File checksums collapsible section */}
          {patchValidationResults?.fileChecksums && modifiedFileCount > 0 && (
            <Collapsible className="mt-2 space-y-1">
              <CollapsibleTrigger className="flex w-full items-center justify-between rounded-sm py-1 text-xs font-medium hover:bg-muted/50">
                <div className="flex items-center">
                  <FileCode className="mr-2 h-3.5 w-3.5 text-muted-foreground" />
                  <span>Modified Files ({modifiedFileCount})</span>
                </div>
                <span className="text-xs text-muted-foreground">Show details</span>
              </CollapsibleTrigger>
              <CollapsibleContent className="text-xs">
                <div className="space-y-1 rounded-md bg-muted/50 p-2">
                  {Object.entries(patchValidationResults.fileChecksums).slice(0, 5).map(([file, checksum]) => (
                    <div key={file} className="flex items-center justify-between text-xs">
                      <span className="font-mono">{file}</span>
                      <span className="text-muted-foreground text-[10px]">
                        {typeof checksum === 'string' ? checksum.substring(0, 8) : ''}
                      </span>
                    </div>
                  ))}
                  {modifiedFileCount > 5 && (
                    <div className="text-xs text-muted-foreground italic">
                      ...and {modifiedFileCount - 5} more files
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      )}
      
      {isEscalated && (
        <div className="mb-3 p-2 border border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900 rounded-md flex items-start gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5" />
          <div className="text-sm">
            <p className="font-medium text-amber-800 dark:text-amber-300">
              {earlyEscalation ? "Early Escalation" : "Escalated after max retries"}
            </p>
            <p className="text-amber-700 dark:text-amber-400">
              {escalationReason || 
               (earlyEscalation ? "Ticket has been escalated early" : 
                `Maximum retry attempts (${maxRetries}) reached`)}
            </p>
            {confidenceScore !== undefined && confidenceScore < 60 && (
              <p className="text-xs mt-1">Confidence score: {confidenceScore}%</p>
            )}
          </div>
        </div>
      )}
      
      {status === 'idle' && !updates && (
        <div className="text-muted-foreground">
          Waiting for QA results...
        </div>
      )}
      
      {status === 'working' && !updates && (
        <div className="space-y-2">
          <p>Updating JIRA and creating PR...</p>
          <div className="h-4 w-full bg-muted overflow-hidden rounded">
            <div 
              className="h-full bg-agent-communicator transition-all duration-300" 
              style={{ width: `${progress || 0}%` }} 
            />
          </div>
        </div>
      )}
      
      {updates && updates.length > 0 && (
        <div className="space-y-4">
          {(prUrl || jiraUrl) && (
            <div className="flex gap-2">
              {prUrl && (
                <Button 
                  variant="secondary" 
                  size="sm" 
                  className="flex items-center gap-1"
                  onClick={() => handleButtonClick(prUrl, 'PR')}
                >
                  <GitPullRequest className="h-4 w-4" />
                  View PR
                </Button>
              )}
              {jiraUrl && (
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="flex items-center gap-1"
                  onClick={() => handleButtonClick(jiraUrl, 'JIRA')}
                >
                  <MessageSquare className="h-4 w-4" />
                  JIRA Ticket
                </Button>
              )}
            </div>
          )}
          
          <Separator />
          
          <ScrollArea className="h-[150px]">
            {updates.map((update, index) => {
              const iconColor = 
                update.type === 'jira' ? 'text-blue-400' : 
                update.type === 'github' ? 'text-purple-400' : 
                update.type === 'system' ? 'text-amber-400' :
                'text-gray-400';
              
              const icon = 
                update.type === 'jira' ? <MessageSquare className="h-4 w-4" /> : 
                update.type === 'github' ? <Github className="h-4 w-4" /> : 
                update.type === 'system' ? <Info className="h-4 w-4" /> :
                '💬';
              
              // Check if message contains certain keywords
              const isEscalationMessage = update.message.includes('escalat') || 
                                         update.message.includes('human review');
                                         
              const isValidationMessage = update.message.includes('Patch validation');
              const isFileListMessage = update.message.includes('Modified') && 
                                       update.message.includes('files with patch');
              
              // Determine message style
              let textStyle = "";
              if (isEscalationMessage) {
                textStyle = "text-amber-600 dark:text-amber-400";
              } else if (isValidationMessage && update.message.includes('failed')) {
                textStyle = "text-red-600 dark:text-red-400";
              } else if (isValidationMessage && update.message.includes('passed')) {
                textStyle = "text-green-600 dark:text-green-400";
              } else if (isFileListMessage) {
                textStyle = "text-blue-600 dark:text-blue-400";
              }
              
              // Special handling for file list update
              const showFileList = isFileListMessage && update.metadata && hasFileList(update.metadata);
                                         
              return (
                <div key={index} className="flex gap-2 mb-2 text-sm">
                  <div className="text-muted-foreground text-xs whitespace-nowrap">
                    {new Date(update.timestamp).toLocaleTimeString()}
                  </div>
                  <div className={`${iconColor} w-4 flex-shrink-0`}>
                    {icon}
                  </div>
                  <div className="flex-1">
                    <div className={textStyle}>
                      {update.message}
                      
                      {update.confidenceScore !== undefined && (
                        <Badge 
                          variant={getConfidenceBadgeVariant(update.confidenceScore)} 
                          className="ml-1 text-xs"
                        >
                          {update.confidenceScore}%
                        </Badge>
                      )}
                    </div>
                    
                    {/* File list collapsible for file modifications */}
                    {showFileList && (
                      <Collapsible className="mt-1">
                        <CollapsibleTrigger className="flex items-center text-xs text-muted-foreground hover:text-foreground">
                          <span>Show files</span>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="pl-2 border-l border-muted mt-1 text-xs">
                          {update.metadata.fileList.map((file: string, i: number) => (
                            <div key={i} className="font-mono">{file}</div>
                          ))}
                          {update.metadata.totalFiles > update.metadata.fileList.length && (
                            <div className="text-muted-foreground">
                              ...and {update.metadata.totalFiles - update.metadata.fileList.length} more
                            </div>
                          )}
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                    
                    {/* File checksums collapsible for validation updates */}
                    {isValidationMessage && update.metadata && hasFileChecksums(update.metadata) && (
                      <Collapsible className="mt-1">
                        <CollapsibleTrigger className="flex items-center text-xs text-muted-foreground hover:text-foreground">
                          <span>File details</span>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="pl-2 border-l border-muted mt-1 text-xs">
                          {Object.entries(update.metadata.fileChecksums).map(([file, checksum]) => (
                            <div key={file} className="flex justify-between">
                              <span className="font-mono">{file}</span>
                              <span className="text-muted-foreground">
                                {typeof checksum === 'string' ? checksum.substring(0, 8) : ''}
                              </span>
                            </div>
                          ))}
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                  </div>
                </div>
              );
            })}
          </ScrollArea>
        </div>
      )}
      
      {status === 'success' && (
        <div className="text-green-500 text-sm pt-2">
          All updates completed successfully.
        </div>
      )}
      
      {status === 'error' && (
        <div className="text-red-500 text-sm pt-2">
          Failed to complete some updates. Check logs for details.
        </div>
      )}
    </AgentCard>
  );
}
