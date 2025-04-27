
import React from 'react';
import { 
  Table, 
  TableHeader, 
  TableRow, 
  TableHead, 
  TableBody, 
  TableCell 
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LogViewer } from '@/components/logs/LogViewer';
import { cn } from '@/lib/utils';
import { TicketListItem } from '@/hooks/useDashboardState';
import { EscalationBadge } from './EscalationBadge';

interface TicketsListProps {
  tickets: TicketListItem[];
  searchQuery: string;
  filterStatus: string | null;
}

export function TicketsList({ tickets, searchQuery, filterStatus }: TicketsListProps) {
  const [expandedLogs, setExpandedLogs] = React.useState<string | null>(null);
  
  const filteredTickets = tickets.filter(ticket => {
    // Apply search filter
    const matchesSearch = !searchQuery || 
      ticket.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.title.toLowerCase().includes(searchQuery.toLowerCase());
      
    // Apply status filter
    const matchesStatus = !filterStatus || ticket.stage === filterStatus;
    
    return matchesSearch && matchesStatus;
  });
  
  const toggleLogView = (ticketId: string) => {
    setExpandedLogs(prev => prev === ticketId ? null : ticketId);
  };
  
  const getStatusBadgeVariant = (status: string) => {
    if (status === 'success') return "default";
    if (status === 'in-progress' || status.includes('attempt')) return "outline"; 
    if (status === 'failed' || status === 'escalated') return "destructive";
    return "secondary";
  };
  
  const getStageBadge = (stage: string) => {
    switch(stage) {
      case 'planning': return <Badge variant="outline">Planning</Badge>;
      case 'development': return <Badge variant="outline">Development</Badge>;
      case 'qa': return <Badge variant="outline">QA</Badge>;
      case 'pr-opened': return <Badge variant="default">PR Opened</Badge>;
      case 'escalated': return <Badge variant="destructive">Escalated</Badge>;
      case 'completed': return <Badge variant="secondary">Completed</Badge>;
      default: return <Badge variant="outline">{stage}</Badge>;
    }
  };
  
  return (
    <div className="space-y-4">
      {filteredTickets.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No tickets match your filters</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ticket ID</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Stage</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last Updated</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTickets.map((ticket) => (
              <React.Fragment key={ticket.id}>
                <TableRow className={cn(expandedLogs === ticket.id && "border-b-0")}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {ticket.id}
                      <EscalationBadge needsReview={!!ticket.needsReview} />
                    </div>
                  </TableCell>
                  <TableCell>{ticket.title}</TableCell>
                  <TableCell>{getStageBadge(ticket.stage)}</TableCell>
                  <TableCell>
                    <Badge variant={getStatusBadgeVariant(ticket.status)}>
                      {ticket.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{new Date(ticket.updatedAt).toLocaleString()}</TableCell>
                  <TableCell className="text-right space-x-2">
                    {ticket.prUrl && (
                      <Button variant="outline" size="sm" asChild>
                        <a href={ticket.prUrl} target="_blank" rel="noopener noreferrer">View PR</a>
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => toggleLogView(ticket.id)}>
                      {expandedLogs === ticket.id ? 'Hide Logs' : 'View Logs'}
                    </Button>
                  </TableCell>
                </TableRow>
                
                {expandedLogs === ticket.id && (
                  <TableRow>
                    <TableCell colSpan={6} className="p-0 border-t-0">
                      <div className="p-4 bg-muted/50 rounded-b-md">
                        <LogViewer ticketId={ticket.id} />
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
