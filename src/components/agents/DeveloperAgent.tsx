
import React from 'react';
import { AgentCard } from './AgentCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';

interface FileDiff {
  filename: string;
  diff: string;
  linesAdded: number;
  linesRemoved: number;
}

interface DeveloperAgentProps {
  status: 'idle' | 'working' | 'success' | 'error' | 'waiting';
  progress?: number;
  attempt?: number;
  maxAttempts?: number;
  diffs?: FileDiff[];
}

export function DeveloperAgent({ status, progress, attempt = 0, maxAttempts = 4, diffs }: DeveloperAgentProps) {
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
      
      {diffs && diffs.length > 0 && (
        <Tabs defaultValue="diff">
          <TabsList className="w-full">
            <TabsTrigger value="diff" className="flex-1">Code Changes</TabsTrigger>
            <TabsTrigger value="summary" className="flex-1">Summary</TabsTrigger>
          </TabsList>
          
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
                <Badge variant="outline">Attempt {attempt}/{maxAttempts}</Badge>
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      )}
      
      {status === 'error' && (
        <div className="text-sm text-red-400 space-y-2">
          <p>Failed to generate a working fix after {attempt} attempts.</p>
          {attempt >= maxAttempts && (
            <p>Maximum attempts reached. Issue will be escalated to human review.</p>
          )}
        </div>
      )}
    </AgentCard>
  );
}
