
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

interface TicketInfoProps {
  ticket: {
    id: string;
    title: string;
    description: string;
    status: string;
    priority: string;
    reporter: string;
    assignee: string | null;
    created: string;
    updated: string;
  } | null;
}

export function TicketInfo({ ticket }: TicketInfoProps) {
  if (!ticket) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No Active Ticket</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Enter a ticket ID to start the fix process.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <CardTitle>
            <span className="text-primary">{ticket.id}</span> - {ticket.title}
          </CardTitle>
          <Badge 
            variant={ticket.status === 'Open' ? 'outline' : 'default'}
            className="ml-2"
          >
            {ticket.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-muted-foreground">Description</h4>
          <p className="text-sm whitespace-pre-line">{ticket.description}</p>
        </div>
        
        <Separator />
        
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="font-semibold text-muted-foreground">Priority</p>
            <p>{ticket.priority}</p>
          </div>
          <div>
            <p className="font-semibold text-muted-foreground">Reporter</p>
            <p>{ticket.reporter}</p>
          </div>
          <div>
            <p className="font-semibold text-muted-foreground">Assignee</p>
            <p>{ticket.assignee || 'Unassigned'}</p>
          </div>
          <div>
            <p className="font-semibold text-muted-foreground">Last Updated</p>
            <p>{new Date(ticket.updated).toLocaleString()}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
