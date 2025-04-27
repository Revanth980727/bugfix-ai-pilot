
import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface EscalationBadgeProps {
  needsReview: boolean;
  className?: string;
}

export function EscalationBadge({ needsReview, className }: EscalationBadgeProps) {
  if (!needsReview) return null;
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={cn("inline-flex items-center", className)}>
            <AlertTriangle className="h-4 w-4 text-destructive animate-pulse" />
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p>This ticket requires human review</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
