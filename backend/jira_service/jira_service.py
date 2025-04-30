
import asyncio
import logging
import signal
import sys
from typing import Dict, Set

from . import config
from .jira_client import JiraClient

# Set up logging
logger = config.setup_logging()

class JiraService:
    def __init__(self):
        """Initialize the JIRA service"""
        try:
            # Validate configuration
            config.validate_config()
            
            # Initialize JIRA client
            self.jira_client = JiraClient()
            
            # Track processed tickets to avoid duplicates
            self.processed_tickets: Set[str] = set()
            
            # Track tickets in progress
            self.tickets_in_progress: Dict[str, Dict] = {}
            
            # Set poll interval
            self.poll_interval = config.JIRA_POLL_INTERVAL
            
            # Flag to control the polling loop
            self.running = False
            
            logger.info(f"JIRA service initialized with poll interval of {self.poll_interval}s")
            
        except (EnvironmentError, ValueError) as e:
            logger.critical(f"Failed to initialize JIRA service: {e}")
            sys.exit(1)
    
    async def process_ticket(self, ticket):
        """Process a single ticket"""
        try:
            ticket_id = ticket["ticket_id"]
            current_status = ticket["status"]
            logger.info(f"Processing ticket {ticket_id} with status '{current_status}'")
            
            # Add to processed tickets to avoid duplicate processing
            self.processed_tickets.add(ticket_id)
            
            # Example: Update ticket status and add comment
            # In a real implementation, this would integrate with the ticket_processor.py to
            # handle the actual processing of the ticket through the agent workflow
            if ticket_id not in self.tickets_in_progress:
                # This is a new ticket, set it to "In Progress" and add initial comment
                comment = "BugFix AI has started processing this ticket. Agent workflow initiated."
                success = await self.jira_client.update_ticket(ticket_id, "In Progress", comment)
                
                if success:
                    self.tickets_in_progress[ticket_id] = ticket
                    logger.info(f"Ticket {ticket_id} marked as In Progress")
                    
                    # Here you would integrate with the rest of your agent workflow
                    # For example, by sending this ticket to your ticket_processor
        except Exception as e:
            logger.error(f"Error processing ticket {ticket.get('ticket_id', 'unknown')}: {e}")
    
    async def poll_tickets(self):
        """Poll JIRA for new bug tickets"""
        try:
            tickets = await self.jira_client.fetch_bug_tickets()
            
            for ticket in tickets:
                ticket_id = ticket.get("ticket_id")
                if ticket_id and ticket_id not in self.processed_tickets:
                    await self.process_ticket(ticket)
        
        except Exception as e:
            logger.error(f"Error during ticket polling: {e}")
    
    async def start_polling(self):
        """Start the polling loop"""
        self.running = True
        logger.info(f"Starting JIRA polling loop every {self.poll_interval} seconds")
        
        while self.running:
            try:
                await self.poll_tickets()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """Stop the polling loop"""
        logger.info("Stopping JIRA service")
        self.running = False

def handle_signals():
    """Set up signal handlers for graceful shutdown"""
    loop = asyncio.get_event_loop()
    service = JiraService()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, service.stop)
    
    return service

async def main():
    """Main entry point for the JIRA service"""
    service = handle_signals()
    await service.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
