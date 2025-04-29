
import React from 'react';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface EscalationBadgeProps {
  className?: string;
  reason?: string;
  retryCount?: number;
  maxRetries?: number;
  isEarly?: boolean;
}

export function EscalationBadge({ 
  className = '', 
  reason, 
  retryCount, 
  maxRetries, 
  isEarly = false 
}: EscalationBadgeProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="destructive" className={`flex items-center gap-1 ${className}`}>
            <AlertTriangle className="h-3 w-3" />
            <span>{isEarly ? "Early Escalation" : "Escalated"}</span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <div className="max-w-xs">
            <p className="font-semibold mb-1">Ticket Escalated</p>
            <p className="text-xs">{reason || 
              (isEarly 
                ? "This ticket was escalated early for human review due to complexity or risk factors."
                : "This ticket has been escalated for human review after multiple fix attempts failed."
              )
            }</p>
            {retryCount !== undefined && maxRetries !== undefined && (
              <p className="text-xs mt-1">Attempts: {retryCount}/{maxRetries}</p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
