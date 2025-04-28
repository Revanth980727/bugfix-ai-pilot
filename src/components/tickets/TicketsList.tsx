
import React from 'react';
import { 
  Table, 
  TableHeader, 
  TableRow, 
  TableHead, 
  TableBody, 
  TableCell 
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TicketListItem } from "@/hooks/useDashboardState";
import { format } from 'date-fns';
import { AlertTriangle, Clock } from 'lucide-react';
import { EscalationBadge } from './EscalationBadge';

interface TicketsListProps {
  tickets: TicketListItem[];
  selectedTicketId: string | null; 
  onSelectTicket: (ticketId: string) => void;
  isLoading?: boolean;
}

export function TicketsList({ 
  tickets, 
  selectedTicketId, 
  onSelectTicket,
  isLoading = false
}: TicketsListProps) {
  // Function to determine status badge color
  const getStatusColor = (status: string): string => {
    const lowerStatus = status.toLowerCase();
    
    if (lowerStatus.includes('complete') || lowerStatus.includes('done')) {
      return 'bg-green-500 hover:bg-green-600';
    } else if (lowerStatus.includes('error') || lowerStatus.includes('fail')) {
      return 'bg-red-500 hover:bg-red-600';
    } else if (lowerStatus.includes('progress')) {
      return 'bg-blue-500 hover:bg-blue-600';
    } else if (lowerStatus.includes('escalat') || lowerStatus.includes('review')) {
      return 'bg-amber-500 hover:bg-amber-600';  
    }
    
    return 'bg-gray-500 hover:bg-gray-600';
  };

  // Function to format date
  const formatDate = (dateString: string): string => {
    try {
      return format(new Date(dateString), 'MMM d, HH:mm');
    } catch (e) {
      return 'Unknown';
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="py-4">
        <CardTitle className="text-lg">Active Tickets</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="hidden md:table-cell">Status</TableHead>
                <TableHead className="hidden sm:table-cell">Updated</TableHead>
                <TableHead className="hidden lg:table-cell">Retry</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8">
                    <div className="flex flex-col items-center justify-center text-muted-foreground">
                      <Clock className="h-6 w-6 animate-pulse mb-2" />
                      <p>Loading tickets...</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : tickets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    No active tickets found
                  </TableCell>
                </TableRow>
              ) : (
                tickets.map((ticket) => (
                  <TableRow 
                    key={ticket.id}
                    className={`cursor-pointer hover:bg-muted/50 ${selectedTicketId === ticket.id ? 'bg-muted' : ''}`}
                    onClick={() => onSelectTicket(ticket.id)}
                  >
                    <TableCell className="font-medium">{ticket.id}</TableCell>
                    <TableCell className="max-w-[200px] truncate">
                      <div className="flex items-center gap-2">
                        {ticket.escalated && (
                          <AlertTriangle className="h-4 w-4 text-amber-500" />
                        )}
                        {ticket.title}
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <Badge className={`${getStatusColor(ticket.status)} text-xs text-white`}>
                        {ticket.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-muted-foreground text-sm">
                      {formatDate(ticket.updatedAt)}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {(ticket.retryCount !== undefined && ticket.maxRetries !== undefined && ticket.retryCount > 0) ? (
                        <Badge variant={ticket.escalated ? "destructive" : "outline"} className="text-xs">
                          {ticket.retryCount}/{ticket.maxRetries}
                        </Badge>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
