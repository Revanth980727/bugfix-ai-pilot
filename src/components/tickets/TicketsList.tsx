
import React from 'react';
import { Card } from '@/components/ui/card';
import { LogViewer, type LogEntry } from '@/components/logs/LogViewer';
import type { Ticket } from '@/types/ticket';
import { TicketListItem } from '@/hooks/useDashboardState';

interface TicketsListProps {
  tickets: Ticket[] | TicketListItem[];
  searchQuery?: string;
  filterStatus?: string | null;
}

export function TicketsList({ tickets, searchQuery = '', filterStatus }: TicketsListProps) {
  const filteredTickets = tickets.filter(ticket => {
    const matchesSearch = 
      ticket.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.id.toLowerCase().includes(searchQuery.toLowerCase());
      
    const matchesStatus = !filterStatus || ticket.status.toLowerCase() === filterStatus.toLowerCase();
    
    return matchesSearch && matchesStatus;
  });

  if (filteredTickets.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No tickets found matching your criteria.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {filteredTickets.map(ticket => (
        <Card key={ticket.id} className="p-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold">{ticket.title}</h3>
              <p className="text-sm text-muted-foreground">{ticket.id}</p>
            </div>
            <span className="text-sm text-muted-foreground">
              {new Date(ticket.created || ticket.updatedAt || '').toLocaleDateString()}
            </span>
          </div>
          
          <div className="mt-4">
            <div className="text-sm">
              <span className="font-medium">Status: </span>
              <span className="text-muted-foreground">{ticket.status}</span>
            </div>
            {/* Show reporter only if it exists (it exists in Ticket but may not in TicketListItem) */}
            {'reporter' in ticket && (
              <div className="text-sm">
                <span className="font-medium">Reporter: </span>
                <span className="text-muted-foreground">{ticket.reporter}</span>
              </div>
            )}
            {/* Show stage if it exists (it exists in TicketListItem but not in Ticket) */}
            {'stage' in ticket && (
              <div className="text-sm">
                <span className="font-medium">Stage: </span>
                <span className="text-muted-foreground">{ticket.stage}</span>
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
