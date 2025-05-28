
import { useState, useEffect } from 'react';
import { fetchTicketData, getProcessingStatus, AgentOutput } from '../data/realData';

export function useRealAgentData(ticketId?: string) {
  const [agentData, setAgentData] = useState<AgentOutput | null>(null);
  const [processingStatus, setProcessingStatus] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch specific ticket data
  const fetchTicket = async (id: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await fetchTicketData(id);
      setAgentData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch ticket data');
    } finally {
      setLoading(false);
    }
  };

  // Fetch processing status
  const fetchStatus = async () => {
    try {
      const status = await getProcessingStatus();
      setProcessingStatus(status);
    } catch (err) {
      console.error('Failed to fetch processing status:', err);
    }
  };

  // Auto-fetch on mount
  useEffect(() => {
    if (ticketId) {
      fetchTicket(ticketId);
    }
    fetchStatus();
  }, [ticketId]);

  // Poll for updates every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStatus();
      if (ticketId && agentData) {
        fetchTicket(ticketId);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [ticketId, agentData]);

  return {
    agentData,
    processingStatus,
    loading,
    error,
    refetch: () => ticketId && fetchTicket(ticketId),
    refreshStatus: fetchStatus
  };
}
