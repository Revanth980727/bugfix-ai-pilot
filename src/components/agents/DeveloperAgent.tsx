import React from 'react';
import { AgentCard } from './AgentCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { AgentStatus } from '@/hooks/useDashboardState';
import { AlertTriangle, CheckCircle, XCircle, BarChart, InfoIcon, Code, FileDigit, GitCommit } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface FileDiff {
  filename: string;
  diff: string;
  linesAdded: number;
  linesRemoved: number;
}

interface DeveloperAgentProps {
  status: AgentStatus;
  progress?: number;
  attempt?: number;
  maxAttempts?: number;
  diffs?: FileDiff[];
  escalated?: boolean;
  escalationReason?: string;
  confidenceScore?: number;
  earlyEscalation?: boolean;
  responseQuality?: 'good' | 'generic' | 'invalid';
  rawResponse?: string | null;
  patchMode?: 'intelligent' | 'line-by-line' | 'direct';
}

export function DeveloperAgent({ 
  status, 
  progress, 
  attempt = 0, 
  maxAttempts = 4, 
  diffs, 
  escalated = false, 
  escalationReason, 
  confidenceScore, 
  earlyEscalation = false,
  responseQuality,
  rawResponse,
  patchMode = 'line-by-line'
}: DeveloperAgentProps) {
  
  // Get color and tooltip for confidence score
  const getConfidenceColor = (score?: number) => {
    if (!score) return "bg-gray-300";
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-yellow-500";
    return "bg-red-500";
  };
  
  const getConfidenceLabel = (score?: number) => {
    if (!score) return "Unknown";
    if (score >= 80) return "High";
    if (score >= 60) return "Medium";
    return "Low";
  };

  const getConfidenceTooltipText = (score?: number) => {
    if (!score) return "No confidence score available";
    if (score >= 80) return "High confidence: The patch is likely to fix the issue with minimal side effects";
    if (score >= 60) return "Medium confidence: The patch addresses the issue but may need further refinement";
    return "Low confidence: The patch may not fully address the issue or could have side effects";
  };

  const getResponseQualityBadge = () => {
    if (!responseQuality) return null;

    let badgeVariant: "default" | "secondary" | "destructive" | "outline";
    let badgeLabel: string;
    let badgeTooltip: string;

    switch (responseQuality) {
      case 'good':
        badgeVariant = "default";
        badgeLabel = "Good Response";
        badgeTooltip = "LLM generated a well-formed patch following the requested format";
        break;
      case 'generic':
        badgeVariant = "secondary";
        badgeLabel = "Generic Response";
        badgeTooltip = "LLM generated a generic response without specific code changes";
        break;
      case 'invalid':
        badgeVariant = "destructive";
        badgeLabel = "Invalid Response";
        badgeTooltip = "LLM generated an invalid patch that couldn't be processed";
        break;
      default:
        return null;
    }

    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant={badgeVariant} className="flex items-center gap-1 cursor-help">
              <FileDigit className="h-3 w-3" />
              <span>{badgeLabel}</span>
            </Badge>
          </TooltipTrigger>
          <TooltipContent side="top">
            <p>{badgeTooltip}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  };
  
  const getPatchModeLabel = (mode?: string) => {
    switch(mode) {
      case 'line-by-line': return "Line-by-line patching";
      case 'intelligent': return "Intelligent patching";
      case 'direct': return "Direct replacement";
      default: return "Standard patching";
    }
  }
  
  const getPatchModeDescription = (mode?: string) => {
    switch(mode) {
      case 'line-by-line': 
        return "Applies changes at the individual line level, preserving as much of the original file as possible";
      case 'intelligent': 
        return "Uses heuristics to determine the best patch strategy based on the diff content";
      case 'direct': 
        return "Directly replaces file content when a clean diff cannot be applied";
      default: 
        return "Standard patching strategy";
    }
  }
  
  return (
    <AgentCard title="Developer" type="developer" status={status} progress={progress}>
      {status === 'idle' && (
        <div className="text-muted-foreground">
          Waiting for planner analysis...
        </div>
      )}
      
      {status === 'working' && !diffs && (
        <div className="space-y-2">
          <div className="flex justify-between">
            <p>Generating fix implementation...</p>
            <Badge variant="outline" className="flex items-center gap-1">
              <InfoIcon className="h-3 w-3" />
              <span>Attempt {attempt}/{maxAttempts}</span>
            </Badge>
          </div>
          <div className="h-4 w-full bg-muted overflow-hidden rounded">
            <div 
              className="h-full bg-agent-developer transition-all duration-300" 
              style={{ width: `${progress || 0}%` }} 
            />
          </div>
        </div>
      )}
      
      {confidenceScore !== undefined && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="mt-2 mb-4 border rounded-md p-3 hover:bg-muted/50 transition-colors">
                <div className="flex justify-between items-center mb-1 text-sm">
                  <div className="flex items-center gap-1">
                    <BarChart className="h-4 w-4" />
                    <span>Confidence Score:</span>
                  </div>
                  <Badge 
                    variant={
                      confidenceScore < 60 ? "destructive" : 
                      (confidenceScore >= 80 ? "default" : "outline")
                    }
                    className={confidenceScore < 60 ? "animate-pulse" : ""}
                  >
                    {getConfidenceLabel(confidenceScore)} ({confidenceScore}%)
                  </Badge>
                </div>
                <Progress 
                  value={confidenceScore} 
                  max={100}
                  className={`h-2 ${getConfidenceColor(confidenceScore)}`}
                />
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-sm">
              <p>{getConfidenceTooltipText(confidenceScore)}</p>
              {confidenceScore < 60 && (
                <p className="mt-1 text-red-500 font-semibold">
                  Low confidence scores may trigger early escalation.
                </p>
              )}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
      
      {patchMode && status !== 'idle' && (
        <div className="mb-4 flex gap-2 items-center">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" className="flex items-center gap-1 cursor-help">
                  <GitCommit className="h-3 w-3" />
                  <span>{getPatchModeLabel(patchMode)}</span>
                </Badge>
              </TooltipTrigger>
              <TooltipContent side="top">
                <p>{getPatchModeDescription(patchMode)}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}
      
      {responseQuality && (
        <div className="mb-4 flex gap-2 items-center">
          <span className="text-sm text-muted-foreground">Response Quality:</span>
          {getResponseQualityBadge()}
        </div>
      )}
      
      {diffs && diffs.length > 0 && (
        <Tabs defaultValue="diff">
          <div className="flex justify-between items-center mb-2">
            <TabsList className="flex-1">
              <TabsTrigger value="diff" className="flex-1">Code Changes</TabsTrigger>
              <TabsTrigger value="summary" className="flex-1">Summary</TabsTrigger>
              {rawResponse && (
                <TabsTrigger value="raw" className="flex-1">
                  <Code className="h-3 w-3 mr-1" />
                  Raw Output
                </TabsTrigger>
              )}
            </TabsList>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge 
                    variant={
                      escalated ? "destructive" : 
                      (earlyEscalation ? "outline" : "outline")
                    } 
                    className={`ml-2 ${earlyEscalation ? "border-red-400" : ""} ${
                      (escalated || earlyEscalation) ? "animate-pulse" : ""
                    }`}
                  >
                    {(escalated || earlyEscalation) && <AlertTriangle className="h-3 w-3 mr-1" />}
                    Attempt {attempt}/{maxAttempts}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-xs">
                  {escalated || earlyEscalation ? (
                    <div className="space-y-1">
                      <p className="font-semibold text-red-500">
                        {earlyEscalation ? "Early Escalation" : "Escalated to Human"}
                      </p>
                      <p className="text-xs">
                        {escalationReason || 
                          (earlyEscalation ? 
                            "This ticket was escalated early due to low confidence or complexity." : 
                            `Maximum attempts (${maxAttempts}) reached without success.`)
                        }
                      </p>
                    </div>
                  ) : (
                    <p>Current attempt: {attempt} of {maxAttempts} maximum tries</p>
                  )}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          
          <TabsContent value="diff">
            <ScrollArea className="h-[300px]">
              {diffs.map((file, index) => (
                <div key={index} className="mb-4">
                  <div className="flex justify-between items-center mb-1">
                    <code className="text-primary text-xs">{file.filename}</code>
                    <div className="text-xs">
                      <span className="text-green-500">+{file.linesAdded}</span>
                      <span> / </span>
                      <span className="text-red-500">-{file.linesRemoved}</span>
                    </div>
                  </div>
                  <div className="bg-muted rounded-md p-2 overflow-x-auto">
                    <pre className="text-xs">
                      <code>{file.diff}</code>
                    </pre>
                  </div>
                </div>
              ))}
            </ScrollArea>
          </TabsContent>
          
          <TabsContent value="summary">
            <ScrollArea className="h-[300px] p-2">
              <div className="space-y-2">
                <p className="text-sm">
                  <span className="text-muted-foreground">Files modified:</span> {diffs.length}
                </p>
                <p className="text-sm">
                  <span className="text-muted-foreground">Total changes:</span>{" "}
                  <span className="text-green-500">+{diffs.reduce((acc, curr) => acc + curr.linesAdded, 0)}</span>
                  <span> / </span>
                  <span className="text-red-500">-{diffs.reduce((acc, curr) => acc + curr.linesRemoved, 0)}</span>
                </p>
                
                {confidenceScore !== undefined && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Confidence Score:</span>
                    <Badge 
                      variant={
                        confidenceScore < 60 ? "destructive" : 
                        (confidenceScore >= 80 ? "default" : "outline")
                      }
                    >
                      {confidenceScore}%
                    </Badge>
                    <span className={
                      confidenceScore < 60 ? "text-red-500 text-xs" : 
                      (confidenceScore >= 80 ? "text-green-500 text-xs" : "text-yellow-500 text-xs")
                    }>
                      ({getConfidenceLabel(confidenceScore)})
                    </span>
                  </div>
                )}
                
                {responseQuality && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Response Quality:</span>
                    {getResponseQualityBadge()}
                  </div>
                )}
                
                <Separator />
                
                <div className="text-sm">
                  <p className="font-semibold mb-1">Modified files:</p>
                  <ul className="list-disc pl-5 space-y-1">
                    {diffs.map((file, index) => (
                      <li key={index}>
                        <code className="text-xs">{file.filename}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </ScrollArea>
          </TabsContent>
          
          {rawResponse && (
            <TabsContent value="raw">
              <ScrollArea className="h-[300px]">
                <div className="bg-muted rounded-md p-2 overflow-x-auto">
                  <pre className="text-xs whitespace-pre-wrap">
                    <code>{rawResponse}</code>
                  </pre>
                </div>
              </ScrollArea>
            </TabsContent>
          )}
        </Tabs>
      )}
      
      {status === 'error' && (
        <div className="text-sm text-red-400 space-y-2 p-3 border border-red-200 rounded-md bg-red-50 dark:bg-red-900/10">
          <p className="flex items-center gap-1">
            <XCircle className="h-4 w-4" />
            Failed to generate a working fix after {attempt} attempt{attempt !== 1 ? 's' : ''}.
          </p>
          {attempt >= maxAttempts && (
            <p className="flex items-center gap-1">
              <AlertTriangle className="h-4 w-4" />
              Maximum attempts reached. Issue has been escalated to human review.
            </p>
          )}
          {responseQuality === 'generic' && (
            <p className="flex items-center gap-1 mt-2">
              <InfoIcon className="h-4 w-4" />
              OpenAI generated a generic response that couldn't be processed.
            </p>
          )}
        </div>
      )}
      
      {status === 'escalated' && (
        <div className="text-sm text-amber-500 space-y-2 p-3 border border-amber-200 rounded-md bg-amber-50 dark:bg-amber-900/10">
          <p className="flex items-center gap-1">
            <AlertTriangle className="h-4 w-4" />
            {earlyEscalation ? "Early escalation" : "Escalated"} to human review{attempt ? ` after ${attempt} attempt${attempt !== 1 ? 's' : ''}` : ""}.
          </p>
          {escalationReason && (
            <p className="pl-6 text-amber-600">
              Reason: {escalationReason}
            </p>
          )}
          {confidenceScore !== undefined && confidenceScore < 60 && (
            <p className="pl-6 text-amber-600">
              Low confidence score: {confidenceScore}%
            </p>
          )}
          {responseQuality === 'generic' && (
            <p className="pl-6 text-amber-600">
              OpenAI generated a generic response that couldn't be processed.
            </p>
          )}
        </div>
      )}
    </AgentCard>
  );
}
