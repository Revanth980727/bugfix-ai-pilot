
import React from 'react';
import { TicketForm } from '../tickets/TicketForm';
import { TicketInfo } from '../tickets/TicketInfo';
import { PlannerAgent } from '../agents/PlannerAgent';
import { DeveloperAgent } from '../agents/DeveloperAgent';
import { QAAgent } from '../agents/QAAgent';
import { CommunicatorAgent } from '../agents/CommunicatorAgent';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useDashboardState } from '@/hooks/useDashboardState';

export function Dashboard() {
  const {
    isProcessing,
    activeTicket,
    plannerStatus,
    developerStatus,
    qaStatus,
    communicatorStatus,
    plannerProgress,
    developerProgress,
    qaProgress,
    communicatorProgress,
    plannerAnalysis,
    diffs,
    testResults,
    updates,
    handleTicketSubmit
  } = useDashboardState();
  
  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Fix Bug</CardTitle>
          </CardHeader>
          <CardContent>
            <TicketForm onSubmit={handleTicketSubmit} isProcessing={isProcessing} />
          </CardContent>
        </Card>
        
        <TicketInfo ticket={activeTicket} />
      </div>
      
      <Separator />
      
      <div className="grid gap-6 md:grid-cols-2">
        <PlannerAgent 
          status={plannerStatus} 
          progress={plannerProgress}
          analysis={plannerAnalysis}
        />
        
        <DeveloperAgent 
          status={developerStatus} 
          progress={developerProgress}
          attempt={1}
          maxAttempts={4}
          diffs={diffs}
        />
      </div>
      
      <div className="grid gap-6 md:grid-cols-2">
        <QAAgent 
          status={qaStatus} 
          progress={qaProgress}
          testResults={testResults}
          summary={testResults ? {
            total: testResults.length,
            passed: testResults.filter(t => t.status === 'pass').length,
            failed: testResults.filter(t => t.status === 'fail').length,
            duration: testResults.reduce((acc, curr) => acc + curr.duration, 0)
          } : undefined}
        />
        
        <CommunicatorAgent 
          status={communicatorStatus} 
          progress={communicatorProgress}
          updates={updates}
          prUrl={updates ? "https://github.com/org/repo/pull/45" : undefined}
          jiraUrl={updates ? "https://jira.company.com/browse/DEMO-123" : undefined}
        />
      </div>
    </div>
  );
}

