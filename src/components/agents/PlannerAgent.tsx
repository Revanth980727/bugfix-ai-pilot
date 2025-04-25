
import React from 'react';
import { AgentCard } from './AgentCard';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';

interface PlannerAgentProps {
  status: 'idle' | 'working' | 'success' | 'error' | 'waiting';
  progress?: number;
  analysis?: {
    affectedFiles?: string[];
    rootCause?: string;
    suggestedApproach?: string;
  };
}

export function PlannerAgent({ status, progress, analysis }: PlannerAgentProps) {
  return (
    <AgentCard title="Planner" type="planner" status={status} progress={progress}>
      {status === 'idle' && (
        <div className="text-muted-foreground">
          Waiting for ticket assignment...
        </div>
      )}
      
      {(status === 'working' || status === 'waiting') && !analysis && (
        <div className="space-y-2">
          <p>Analyzing ticket information and identifying affected code...</p>
          <div className="h-4 w-full bg-muted overflow-hidden rounded">
            <div 
              className="h-full bg-agent-planner transition-all duration-300" 
              style={{ width: `${progress || 0}%` }} 
            />
          </div>
        </div>
      )}
      
      {analysis && (
        <Tabs defaultValue="files" className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="files" className="flex-1">Affected Files</TabsTrigger>
            <TabsTrigger value="cause" className="flex-1">Root Cause</TabsTrigger>
            <TabsTrigger value="approach" className="flex-1">Approach</TabsTrigger>
          </TabsList>
          
          <TabsContent value="files">
            <ScrollArea className="h-[200px]">
              {analysis.affectedFiles?.length ? (
                <ul className="space-y-1">
                  {analysis.affectedFiles.map((file, index) => (
                    <li key={index} className="text-sm p-1 rounded hover:bg-muted">
                      <code>{file}</code>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground">No files have been identified yet.</p>
              )}
            </ScrollArea>
          </TabsContent>
          
          <TabsContent value="cause">
            <ScrollArea className="h-[200px]">
              {analysis.rootCause ? (
                <div className="text-sm whitespace-pre-line">{analysis.rootCause}</div>
              ) : (
                <p className="text-muted-foreground">Root cause analysis not available.</p>
              )}
            </ScrollArea>
          </TabsContent>
          
          <TabsContent value="approach">
            <ScrollArea className="h-[200px]">
              {analysis.suggestedApproach ? (
                <div className="text-sm whitespace-pre-line">{analysis.suggestedApproach}</div>
              ) : (
                <p className="text-muted-foreground">Suggested approach not available.</p>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>
      )}
    </AgentCard>
  );
}
