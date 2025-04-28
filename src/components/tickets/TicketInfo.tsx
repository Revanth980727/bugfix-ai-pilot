
import React from 'react';
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Ticket } from "@/types/ticket";
import { CalendarClock } from 'lucide-react';
import { format } from 'date-fns';
import { EscalationBadge } from './EscalationBadge';

interface TicketInfoProps {
  ticket: Ticket;
  className?: string;
}

const getPriorityColor = (priority: string): string => {
  switch (priority.toLowerCase()) {
    case "high":
      return "bg-red-500";
    case "medium":
      return "bg-yellow-500";
    case "low":
      return "bg-green-500";
    default:
      return "bg-blue-500";
  }
};

const getStatusColor = (status: string): string => {
  const statusLower = status.toLowerCase();
  if (statusLower.includes("completed") || statusLower.includes("done")) {
    return "bg-green-500 hover:bg-green-600";
  }
  if (statusLower.includes("error") || statusLower.includes("fail")) {
    return "bg-red-500 hover:bg-red-600";
  }
  if (statusLower.includes("progress") || statusLower.includes("processing")) {
    return "bg-blue-500 hover:bg-blue-600";
  }
  if (statusLower.includes("escalated") || statusLower.includes("review")) {
    return "bg-amber-500 hover:bg-amber-600";
  }
  return "bg-gray-500 hover:bg-gray-600";
};

export function TicketInfo({ ticket, className = "" }: TicketInfoProps) {
  const statusColor = getStatusColor(ticket.status);
  const priorityColor = getPriorityColor(ticket.priority);
  const isEscalated = ticket.escalated || ticket.status?.toLowerCase()?.includes('escalated');
  
  const formattedDate = ticket.updated ? format(new Date(ticket.updated), 'MMM d, yyyy h:mm a') : '';

  return (
    <Card className={`${className}`}>
      <CardContent className="p-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="text-xl font-semibold">{ticket.title || ticket.id}</h2>
            <div className="flex items-center text-xs text-muted-foreground gap-1 mt-1">
              <CalendarClock className="h-3 w-3" />
              <span>{formattedDate}</span>
            </div>
          </div>
          
          <div className="flex flex-wrap gap-2">
            {isEscalated && <EscalationBadge />}
            
            {ticket.current_attempt > 0 && (
              <Badge variant="outline" className={isEscalated ? 'border-amber-500 text-amber-500' : ''}>
                Attempt {ticket.current_attempt}/{ticket.max_attempts || 4}
              </Badge>
            )}
            
            {ticket.priority && (
              <Badge className={`${priorityColor} text-white`}>
                {ticket.priority}
              </Badge>
            )}
            
            <Badge className={`${statusColor} text-white`}>
              {ticket.status}
            </Badge>
          </div>
        </div>
        
        {ticket.description && (
          <div className="mt-4 text-sm text-muted-foreground">
            <p>{ticket.description}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

