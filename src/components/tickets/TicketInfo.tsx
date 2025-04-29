
import React from 'react';
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Ticket } from "@/types/ticket";
import { CalendarClock, AlertTriangle } from 'lucide-react';
import { format } from 'date-fns';
import { EscalationBadge } from './EscalationBadge';
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Progress } from "@/components/ui/progress";

interface TicketInfoProps {
  ticket: Ticket | null;
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
  // If no ticket data is available, show empty card with a message
  if (!ticket) {
    return (
      <Card className={`${className}`}>
        <CardContent className="p-4">
          <div className="text-center py-4 text-muted-foreground">
            <p>No ticket selected</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const statusColor = getStatusColor(ticket.status);
  const priorityColor = getPriorityColor(ticket.priority);
  const isEscalated = ticket.escalated || ticket.status?.toLowerCase()?.includes('escalated');
  const isEarlyEscalation = isEscalated && (ticket.current_attempt || 0) < (ticket.max_attempts || 4);
  
  const formattedDate = ticket.updated ? format(new Date(ticket.updated), 'MMM d, yyyy h:mm a') : '';

  const retryPercentage = ticket.max_attempts 
    ? Math.min((ticket.current_attempt || 0) / ticket.max_attempts * 100, 100) 
    : 0;

  return (
    <Card className={`${className}`}>
      <CardContent className="p-4">
        {isEscalated && (
          <Alert variant="destructive" className="mb-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {isEarlyEscalation 
                ? "This ticket has been early escalated for human review due to complexity factors" 
                : "This ticket has been escalated for human review after multiple fix attempts failed"}
            </AlertDescription>
          </Alert>
        )}
        
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="text-xl font-semibold">{ticket.title || ticket.id}</h2>
            <div className="flex items-center text-xs text-muted-foreground gap-1 mt-1">
              <CalendarClock className="h-3 w-3" />
              <span>{formattedDate}</span>
            </div>
          </div>
          
          <div className="flex flex-wrap gap-2">
            {isEscalated && (
              <EscalationBadge 
                isEarly={isEarlyEscalation} 
                retryCount={ticket.current_attempt} 
                maxRetries={ticket.max_attempts} 
              />
            )}
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge 
                    variant={isEscalated ? "destructive" : "outline"} 
                    className="flex items-center space-x-1"
                  >
                    <span>Attempt:</span>
                    <span>{ticket.current_attempt || 0}/{ticket.max_attempts || 4}</span>
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <div className="space-y-1 w-40">
                    <p className="text-xs">
                      Retry progress: {ticket.current_attempt || 0} of {ticket.max_attempts || 4} attempts used
                    </p>
                    <Progress value={retryPercentage} className="h-1" />
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
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
