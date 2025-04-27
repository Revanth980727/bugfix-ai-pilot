
import React, { useState, useEffect } from 'react';
import { TicketForm } from '../tickets/TicketForm';
import { TicketInfo } from '../tickets/TicketInfo';
import { PlannerAgent } from '../agents/PlannerAgent';
import { DeveloperAgent } from '../agents/DeveloperAgent';
import { QAAgent } from '../agents/QAAgent';
import { CommunicatorAgent } from '../agents/CommunicatorAgent';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useDashboardState } from '@/hooks/useDashboardState';
import { TicketsList } from '../tickets/TicketsList';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Search, Filter } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';

export function Dashboard() {
  const [view, setView] = useState<'current' | 'list'>('current');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  
  const { resolvedTheme, setTheme } = useTheme();
  
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
    handleTicketSubmit,
    ticketsList,
    fetchTickets,
    currentAttempt,
    maxAttempts
  } = useDashboardState();

  // Poll for ticket updates every 10 seconds
  useEffect(() => {
    fetchTickets();
    
    const interval = setInterval(() => {
      fetchTickets();
    }, 10000);
    
    return () => clearInterval(interval);
  }, [fetchTickets]);
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <Tabs value={view} onValueChange={(v) => setView(v as 'current' | 'list')} className="w-[400px]">
          <TabsList>
            <TabsTrigger value="current">Current Ticket</TabsTrigger>
            <TabsTrigger value="list">Tickets List</TabsTrigger>
          </TabsList>
        </Tabs>
        
        <div className="flex items-center space-x-2">
          <Switch 
            id="theme-mode" 
            checked={resolvedTheme === 'dark'} 
            onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
          />
          <Label htmlFor="theme-mode">Dark Mode</Label>
        </div>
      </div>
      
      {/* Important: All TabsContent components must be within the same Tabs component as their corresponding TabsTrigger */}
      <Tabs value={view} onValueChange={(v) => setView(v as 'current' | 'list')} className="mt-0">
        <TabsContent value="current">
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
              attempt={currentAttempt}
              maxAttempts={maxAttempts}
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
        </TabsContent>
        
        <TabsContent value="list">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle>Tickets</CardTitle>
              <div className="flex space-x-2">
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search tickets..."
                    className="pl-8 w-[200px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="relative">
                  <Filter className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <select
                    className="h-10 pl-8 pr-4 rounded-md border border-input bg-background text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    value={filterStatus || ''}
                    onChange={(e) => setFilterStatus(e.target.value || null)}
                  >
                    <option value="">All Status</option>
                    <option value="planning">Planning</option>
                    <option value="development">Development</option>
                    <option value="qa">QA</option>
                    <option value="pr-opened">PR Opened</option>
                    <option value="escalated">Escalated</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <TicketsList 
                tickets={ticketsList} 
                searchQuery={searchQuery}
                filterStatus={filterStatus}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
