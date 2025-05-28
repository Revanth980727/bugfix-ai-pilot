
import React from 'react';
import { AgentCard } from './AgentCard';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AgentStatus } from '@/hooks/useDashboardState';
import { Badge } from '@/components/ui/badge';
import { AffectedFile } from '@/types/ticket';
import { CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface PlannerAgentProps {
  status: AgentStatus;
  progress?: number;
  analysis?: {
    bug_summary?: string;
    affected_files?: Array<string | AffectedFile>;
    error_type?: string;
    using_fallback?: boolean;
    ticket_id?: string;
    repository_info?: {
      total_files: number;
      analyzed_files: number;
      file_types: string[];
    };
  };
}

const isAffectedFile = (item: any): item is AffectedFile => {
  return typeof item === 'object' && 'file' in item && 'valid' in item;
};

export function PlannerAgent({ status, progress, analysis }: PlannerAgentProps) {
  const bugSummary = analysis?.bug_summary;
  const affectedFiles = analysis?.affected_files || [];
  const errorType = analysis?.error_type;
  const usingFallback = analysis?.using_fallback;
  const repositoryInfo = analysis?.repository_info;
  
  const isIncomplete = analysis && (!bugSummary || !errorType || affectedFiles.length === 0);
  
  return (
    <AgentCard title="Planner" type="planner" status={status} progress={progress}>
      {status === 'idle' && (
        <div className="text-muted-foreground">
          Waiting for ticket assignment...
        </div>
      )}
      
      {(status === 'working' || status === 'waiting') && !analysis && (
        <div className="space-y-2">
          <p>Analyzing repository and identifying affected code...</p>
          {repositoryInfo && (
            <div className="text-xs text-muted-foreground">
              Repository: {repositoryInfo.total_files} files, {repositoryInfo.file_types.join(', ')}
            </div>
          )}
          <div className="h-4 w-full bg-muted overflow-hidden rounded">
            <div 
              className="h-full bg-agent-planner transition-all duration-300" 
              style={{ width: `${progress || 0}%` }} 
            />
          </div>
        </div>
      )}
      
      {analysis && (
        <div className="space-y-4">
          {usingFallback && (
            <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300">
              Fallback Analysis
            </Badge>
          )}
          
          {isIncomplete && (
            <div className="flex items-center gap-2 text-amber-700 bg-amber-50 p-2 rounded">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-xs">Analysis may be incomplete</span>
            </div>
          )}
          
          <Tabs defaultValue="summary" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="summary" className="flex-1">Summary</TabsTrigger>
              <TabsTrigger value="files" className="flex-1">Affected Files</TabsTrigger>
              {errorType && (
                <TabsTrigger value="error" className="flex-1">Error Type</TabsTrigger>
              )}
              {repositoryInfo && (
                <TabsTrigger value="repo" className="flex-1">Repository</TabsTrigger>
              )}
            </TabsList>
            
            <TabsContent value="summary">
              <ScrollArea className="h-[200px]">
                {bugSummary ? (
                  <div className="text-sm whitespace-pre-line">{bugSummary}</div>
                ) : (
                  <p className="text-muted-foreground">Bug summary not available.</p>
                )}
              </ScrollArea>
            </TabsContent>
            
            <TabsContent value="files">
              <ScrollArea className="h-[200px]">
                {affectedFiles?.length ? (
                  <ul className="space-y-1">
                    {affectedFiles.map((file, index) => (
                      <li key={index} className="text-sm p-1 rounded hover:bg-muted flex items-center gap-2">
                        {isAffectedFile(file) ? (
                          <>
                            {file.valid ? (
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-500" />
                            )}
                            <code className={file.valid ? "" : "text-red-500"}>{file.file}</code>
                            {!file.valid && (
                              <Badge variant="outline" className="ml-1 bg-red-50 border-red-200 text-red-600 text-xs">
                                Not Found
                              </Badge>
                            )}
                          </>
                        ) : (
                          <code>{file}</code>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">No files identified in repository analysis.</p>
                )}
              </ScrollArea>
            </TabsContent>
            
            {errorType && (
              <TabsContent value="error">
                <ScrollArea className="h-[200px]">
                  <div className="text-sm font-medium">{errorType}</div>
                </ScrollArea>
              </TabsContent>
            )}
            
            {repositoryInfo && (
              <TabsContent value="repo">
                <ScrollArea className="h-[200px]">
                  <div className="space-y-2 text-sm">
                    <div>Total files in repository: {repositoryInfo.total_files}</div>
                    <div>Files analyzed: {repositoryInfo.analyzed_files}</div>
                    <div>File types: {repositoryInfo.file_types.join(', ')}</div>
                  </div>
                </ScrollArea>
              </TabsContent>
            )}
          </Tabs>
        </div>
      )}
    </AgentCard>
  );
}
