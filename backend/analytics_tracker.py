
import os
import csv
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsTracker:
    """
    Tracks analytics data for tickets, retries, and escalations
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the analytics tracker
        
        Args:
            output_dir: Directory to store analytics logs (defaults to ./analytics_logs)
        """
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "analytics_logs")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize CSV log file if it doesn't exist
        self.csv_log_path = os.path.join(self.output_dir, "ticket_analytics.csv")
        self._initialize_csv()
        
        # Also maintain a JSON log for more detailed records
        self.json_log_path = os.path.join(self.output_dir, "ticket_analytics.jsonl")
        
        logger.info(f"Analytics tracker initialized: CSV log at {self.csv_log_path}, JSON log at {self.json_log_path}")
        
    def _initialize_csv(self):
        """Initialize the CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_log_path):
            with open(self.csv_log_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    'ticket_id',
                    'timestamp',
                    'total_retries',
                    'final_status',
                    'confidence_score',
                    'early_escalation',
                    'escalation_reason'
                ])
        
    def log_ticket_result(
        self,
        ticket_id: str,
        total_retries: int,
        final_status: str,
        confidence_score: Optional[int] = None,
        escalation_reason: Optional[str] = None,
        qa_failure_summary: Optional[str] = None,
        early_escalation: bool = False,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Log a ticket processing result
        
        Args:
            ticket_id: The JIRA ticket ID
            total_retries: How many retry attempts were made
            final_status: Final status (success, escalated, failed)
            confidence_score: Developer agent confidence score (0-100)
            escalation_reason: Why the ticket was escalated (if applicable)
            qa_failure_summary: Summary of QA test failures (if applicable)
            early_escalation: Whether ticket was escalated early (before max retries)
            additional_data: Any additional data to include in the JSON log
        """
        try:
            timestamp = datetime.now().isoformat()
            
            # Log to CSV (simpler format)
            with open(self.csv_log_path, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    ticket_id,
                    timestamp,
                    total_retries,
                    final_status,
                    confidence_score or 'N/A',
                    early_escalation,
                    escalation_reason or 'N/A'
                ])
            
            # Log to JSON (more detailed)
            log_entry = {
                'ticket_id': ticket_id,
                'timestamp': timestamp,
                'total_retries': total_retries,
                'final_status': final_status,
                'confidence_score': confidence_score,
                'early_escalation': early_escalation,
                'escalation_reason': escalation_reason,
                'qa_failure_summary': qa_failure_summary
            }
            
            # Add additional data if provided
            if additional_data:
                log_entry.update(additional_data)
                
            # Append to JSONL file (one JSON object per line)
            with open(self.json_log_path, 'a') as jsonfile:
                jsonfile.write(json.dumps(log_entry) + '\n')
                
            logger.info(f"Logged analytics for ticket {ticket_id}: {final_status} with {total_retries} retries")
            
        except Exception as e:
            logger.error(f"Error logging analytics for ticket {ticket_id}: {str(e)}")

# Singleton instance
_analytics_tracker = None

def get_analytics_tracker() -> AnalyticsTracker:
    """Get the singleton instance of the analytics tracker"""
    global _analytics_tracker
    if _analytics_tracker is None:
        _analytics_tracker = AnalyticsTracker()
    return _analytics_tracker
