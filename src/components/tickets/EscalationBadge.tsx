
import React from 'react';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface EscalationBadgeProps {
  className?: string;
}

export function EscalationBadge({ className = '' }: EscalationBadgeProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="destructive" className={`flex items-center gap-1 ${className}`}>
            <AlertTriangle className="h-3 w-3" />
            <span>Escalated</span>
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs">This ticket has been escalated for human review after multiple fix attempts failed</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
