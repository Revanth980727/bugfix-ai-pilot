
import React from 'react';
import { AgentCard } from './AgentCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { GitPullRequest, MessageSquare } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

interface Update {
  timestamp: string;
  message: string;
  type: 'jira' | 'github' | 'system';
}

interface CommunicatorAgentProps {
  status: 'idle' | 'working' | 'success' | 'error' | 'waiting';
  progress?: number;
  updates?: Update[];
  prUrl?: string;
  jiraUrl?: string;
}

export function CommunicatorAgent({ status, progress, updates, prUrl, jiraUrl }: CommunicatorAgentProps) {
  return (
    <AgentCard title="Communicator" type="communicator" status={status} progress={progress}>
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
                <Button variant="secondary" size="sm" className="flex items-center gap-1">
                  <GitPullRequest className="h-4 w-4" />
                  View PR
                </Button>
              )}
              {jiraUrl && (
                <Button variant="outline" size="sm" className="flex items-center gap-1">
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
                update.type === 'github' ? 'text-purple-400' : 'text-gray-400';
              
              return (
                <div key={index} className="flex gap-2 mb-2 text-sm">
                  <div className="text-muted-foreground text-xs whitespace-nowrap">
                    {new Date(update.timestamp).toLocaleTimeString()}
                  </div>
                  <div className={`${iconColor} w-4 flex-shrink-0`}>
                    {update.type === 'jira' && '🔄'}
                    {update.type === 'github' && '🔀'}
                    {update.type === 'system' && '💬'}
                  </div>
                  <div className="flex-1">{update.message}</div>
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
