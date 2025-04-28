
import React from 'react';
import { AgentCard } from './AgentCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { AgentStatus } from '@/hooks/useDashboardState';
import { AlertTriangle, CheckCircle, XCircle, BarChart } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

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
  earlyEscalation = false 
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
            <Badge variant="outline">Attempt {attempt}/{maxAttempts}</Badge>
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
        <div className="mt-2 mb-4">
          <div className="flex justify-between items-center mb-1 text-sm">
            <div className="flex items-center gap-1">
              <BarChart className="h-4 w-4" />
              <span>Confidence Score:</span>
            </div>
            <Badge variant={confidenceScore < 60 ? "destructive" : (confidenceScore >= 80 ? "default" : "outline")}>
              {getConfidenceLabel(confidenceScore)} ({confidenceScore}%)
            </Badge>
          </div>
          <Progress 
            value={confidenceScore} 
            max={100}
            className={`h-2 ${getConfidenceColor(confidenceScore)}`}
          />
        </div>
      )}
      
      {diffs && diffs.length > 0 && (
        <Tabs defaultValue="diff">
          <div className="flex justify-between items-center mb-2">
            <TabsList className="flex-1">
              <TabsTrigger value="diff" className="flex-1">Code Changes</TabsTrigger>
              <TabsTrigger value="summary" className="flex-1">Summary</TabsTrigger>
            </TabsList>
            <Badge 
              variant={
                escalated ? "destructive" : 
                (earlyEscalation ? "outline" : "outline")
              } 
              className={`ml-2 ${earlyEscalation ? "border-red-400" : ""}`}
            >
              {(escalated || earlyEscalation) && <AlertTriangle className="h-3 w-3 mr-1" />}
              Attempt {attempt}/{maxAttempts}
            </Badge>
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
                  <p className="text-sm">
                    <span className="text-muted-foreground">Confidence Score:</span>{" "}
                    <span className={
                      confidenceScore < 60 ? "text-red-500" : 
                      (confidenceScore >= 80 ? "text-green-500" : "text-yellow-500")
                    }>
                      {confidenceScore}%
                    </span>
                  </p>
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
        </Tabs>
      )}
      
      {status === 'error' && (
        <div className="text-sm text-red-400 space-y-2">
          <p>Failed to generate a working fix after {attempt} attempts.</p>
          {attempt >= maxAttempts && (
            <p className="flex items-center gap-1">
              <AlertTriangle className="h-4 w-4" />
              Maximum attempts reached. Issue has been escalated to human review.
            </p>
          )}
        </div>
      )}
      
      {status === 'escalated' && (
        <div className="text-sm text-amber-500 space-y-2">
          <p className="flex items-center gap-1">
            <AlertTriangle className="h-4 w-4" />
            {earlyEscalation ? "Early escalation" : "Escalated"} to human review{attempt ? ` after ${attempt} attempt${attempt !== 1 ? 's' : ''}` : ""}.
          </p>
          {escalationReason && (
            <p className="pl-6 text-amber-600">
              Reason: {escalationReason}
            </p>
          )}
        </div>
      )}
    </AgentCard>
  );
}
