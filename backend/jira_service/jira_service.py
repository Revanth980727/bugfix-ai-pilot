import asyncio
import logging
import signal
import sys
import traceback
from typing import Dict, Set

from . import config
from .jira_client import JiraClient
# Import the agent controller to process tickets
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_framework.planner_agent import PlannerAgent
from agent_framework.developer_agent import DeveloperAgent
from agent_framework.qa_agent import QAAgent
from agent_framework.communicator_agent import CommunicatorAgent

# Set up logging
logger = config.setup_logging()

class JiraService:
    def __init__(self):
        """Initialize the JIRA service"""
        try:
            # Validate configuration
            config.validate_config()
            
            logger.info("Initializing JIRA service and agent framework...")
            
            # Initialize JIRA client
            self.jira_client = JiraClient()
            
            # Initialize agents for processing
            logger.info("Setting up agent instances...")
            self.planner_agent = PlannerAgent()
            self.developer_agent = DeveloperAgent()
            self.qa_agent = QAAgent()
            self.communicator_agent = CommunicatorAgent()
            
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
            # First ensure ticket is a valid dictionary
            if not ticket or not isinstance(ticket, dict):
                logger.error("Invalid ticket object received: not a dictionary or None")
                return
                
            ticket_id = ticket.get("ticket_id")
            if not ticket_id:
                logger.error("Invalid ticket: missing ticket_id")
                return
                
            current_status = ticket.get("status", "Unknown")
            logger.info(f"Processing ticket {ticket_id} with status '{current_status}'")
            
            # Check if we've already processed this ticket
            if ticket_id in self.processed_tickets:
                logger.info(f"Ticket {ticket_id} has already been processed. Skipping.")
                return
            
            # Add to processed tickets to avoid duplicate processing
            self.processed_tickets.add(ticket_id)
            
            # Mark ticket as in progress in JIRA
            if ticket_id not in self.tickets_in_progress:
                # This is a new ticket, set it to "In Progress" and add initial comment
                comment = "BugFix AI has started processing this ticket. Agent workflow initiated."
                success = await self.jira_client.update_ticket(ticket_id, "In Progress", comment)
                
                if success:
                    self.tickets_in_progress[ticket_id] = ticket
                    logger.info(f"Ticket {ticket_id} marked as In Progress")
                    
                    # Create a new task so it runs independently
                    # Important: We need to ensure this is actually called
                    logger.info(f"Starting agent workflow for ticket {ticket_id}...")
                    task = asyncio.create_task(self.run_agent_workflow(ticket))
                    # Add a callback to handle errors
                    task.add_done_callback(lambda t: self.handle_workflow_completion(t, ticket_id))
                else:
                    logger.error(f"Failed to update ticket {ticket_id} status to In Progress")
            else:
                logger.info(f"Ticket {ticket_id} is already in progress")
        except Exception as e:
            logger.error(f"Error processing ticket {ticket.get('ticket_id', 'unknown')}: {e}")
            logger.error(traceback.format_exc())
    
    def handle_workflow_completion(self, task, ticket_id):
        """Handle completion of agent workflow task"""
        try:
            # Check if the task raised an exception
            if task.exception():
                logger.error(f"Agent workflow for ticket {ticket_id} failed with exception: {task.exception()}")
        except asyncio.CancelledError:
            logger.warning(f"Agent workflow for ticket {ticket_id} was cancelled")
        except Exception as e:
            logger.error(f"Error handling workflow completion for {ticket_id}: {e}")
            logger.error(traceback.format_exc())
    
    async def run_agent_workflow(self, ticket):
        """Run the complete agent workflow for a ticket"""
        if not ticket or not isinstance(ticket, dict):
            logger.error("Invalid ticket object passed to run_agent_workflow")
            return
            
        ticket_id = ticket.get("ticket_id")
        if not ticket_id:
            logger.error("Invalid ticket: missing ticket_id")
            return
            
        logger.info(f"==== STARTING AGENT WORKFLOW FOR TICKET {ticket_id} ====")
        
        try:
            # Step 1: Run the planner agent
            logger.info(f"Running planner agent for ticket {ticket_id}")
            
            # Debug log the ticket content
            logger.info(f"Ticket content for planner: {ticket}")
            
            # Create input for planner with validation
            planner_input = {
                "ticket_id": ticket_id,
                "title": ticket.get("title", "No title"),
                "description": ticket.get("description", "No description"),
                "status": ticket.get("status", "Unknown")
            }
            logger.info(f"Planner input: {planner_input}")
            
            # Run planner (synchronous)
            try:
                logger.info("Executing planner agent...")
                # Create a more robust way to run the planner
                if hasattr(self.planner_agent, 'run') and callable(self.planner_agent.run):
                    planner_result = self.planner_agent.run(planner_input)
                    logger.info(f"Planner agent returned: {planner_result}")
                else:
                    logger.error("Planner agent doesn't have a 'run' method")
                    planner_result = None
            except Exception as e:
                logger.error(f"Error running planner agent: {e}")
                logger.error(traceback.format_exc())
                await self.jira_client.update_ticket(
                    ticket_id, 
                    "Needs Review", 
                    f"Error running planner agent: {str(e)}"
                )
                return
            
            if not planner_result:
                logger.warning(f"Planner agent returned no result for ticket {ticket_id}")
                await self.jira_client.update_ticket(
                    ticket_id, 
                    "Needs Review", 
                    "BugFix AI couldn't analyze this ticket properly: No result from planner"
                )
                return
            
            # Only if the planner result is a dictionary, check for using_fallback
            if isinstance(planner_result, dict):
                if planner_result.get("using_fallback", False):
                    logger.warning(f"Planner agent used fallback for ticket {ticket_id}")
                    await self.jira_client.update_ticket(
                        ticket_id, 
                        "Needs Review", 
                        f"BugFix AI couldn't analyze this ticket properly: {planner_result.get('bug_summary', 'Unknown error')}"
                    )
                    return
            else:
                logger.warning(f"Unexpected planner result type: {type(planner_result)}")
                await self.jira_client.update_ticket(
                    ticket_id, 
                    "Needs Review", 
                    "BugFix AI received unexpected response type from planner"
                )
                return
            
            # Step 2: Run the developer agent with the planner results
            max_retries = 4
            success = False
            
            for attempt in range(1, max_retries + 1):
                logger.info(f"Running developer agent for ticket {ticket_id} (attempt {attempt}/{max_retries})")
                
                # Add the ticket_id to planner_result
                developer_input = {**planner_result, "ticket_id": ticket_id}
                logger.info(f"Developer input: {developer_input}")
                
                try:
                    logger.info("Executing developer agent...")
                    developer_result = self.developer_agent.run(developer_input)
                    logger.info(f"Developer agent returned: {developer_result}")
                except Exception as e:
                    logger.error(f"Error running developer agent: {e}")
                    logger.error(traceback.format_exc())
                    if attempt == max_retries:
                        await self.jira_client.update_ticket(
                            ticket_id, 
                            "Needs Review", 
                            f"Error running developer agent after {max_retries} attempts: {str(e)}"
                        )
                        return
                    continue
                
                # Step 3: Run the QA agent to test the fix
                logger.info(f"Running QA agent for ticket {ticket_id} (attempt {attempt}/{max_retries})")
                qa_input = {"ticket_id": ticket_id}
                logger.info(f"QA input: {qa_input}")
                
                try:
                    logger.info("Executing QA agent...")
                    qa_result = self.qa_agent.run(qa_input)
                    logger.info(f"QA agent returned: {qa_result}")
                except Exception as e:
                    logger.error(f"Error running QA agent: {e}")
                    logger.error(traceback.format_exc())
                    if attempt == max_retries:
                        await self.jira_client.update_ticket(
                            ticket_id, 
                            "Needs Review", 
                            f"Error running QA agent after {max_retries} attempts: {str(e)}"
                        )
                        return
                    continue
                
                # Check if tests passed - ensure qa_result is a dictionary and has 'passed' key
                if isinstance(qa_result, dict) and qa_result.get("passed", False):
                    success = True
                    break
                    
                # If this is the last attempt and tests failed, escalate
                if attempt == max_retries:
                    logger.warning(f"All {max_retries} attempts failed for ticket {ticket_id}")
                    break
                    
                # Add a comment about the failed attempt
                await self.jira_client.update_ticket(
                    ticket_id,
                    "In Progress",
                    f"Attempt {attempt}/{max_retries} failed. Retrying with improved fix."
                )
                
                # Wait before the next attempt
                await asyncio.sleep(5)
            
            # Step 4: Run the communicator agent to update the ticket
            logger.info(f"Running communicator agent for ticket {ticket_id}")
            communicator_input = {
                "ticket_id": ticket_id,
                "success": success,
                "planner_result": planner_result,
                "qa_result": qa_result if 'qa_result' in locals() else {"passed": False}
            }
            logger.info(f"Communicator input: {communicator_input}")
            
            try:
                logger.info("Executing communicator agent...")
                # Fix: Make sure to await the coroutine if run() returns a coroutine object
                communicator_result = await self._await_coroutine_if_needed(self.communicator_agent.run(communicator_input))
                logger.info(f"Communicator agent returned: {communicator_result}")
            except Exception as e:
                logger.error(f"Error running communicator agent: {e}")
                logger.error(traceback.format_exc())
                
                # Even if communicator fails, we should update the ticket status
                if success:
                    await self.jira_client.update_ticket(
                        ticket_id,
                        "Done",  # Changed from "Done" to match what worked in logs
                        "BugFix AI successfully fixed the issue, but failed to create PR."
                    )
                else:
                    await self.jira_client.update_ticket(
                        ticket_id,
                        "Needs Review",
                        f"BugFix AI couldn't fix the issue after {max_retries} attempts. Human review needed."
                    )
                return
            
            # Update the ticket status based on the final result
            if success:
                await self.jira_client.update_ticket(
                    ticket_id,
                    "Done",  # Changed from "Done" to match what worked in logs
                    "BugFix AI successfully fixed the issue. PR created with the fix."
                )
            else:
                await self.jira_client.update_ticket(
                    ticket_id,
                    "Needs Review",
                    f"BugFix AI couldn't fix the issue after {max_retries} attempts. Human review needed."
                )
                
        except Exception as e:
            logger.error(f"Error in agent workflow for ticket {ticket_id}: {str(e)}")
            logger.error(traceback.format_exc())
            # Update ticket as failed
            await self.jira_client.update_ticket(
                ticket_id,
                "Needs Review",
                f"Error in agent workflow: {str(e)}"
            )
        finally:
            logger.info(f"==== COMPLETED AGENT WORKFLOW FOR TICKET {ticket_id} ====")
    
    async def _await_coroutine_if_needed(self, result):
        """Helper method to await a result if it's a coroutine"""
        if hasattr(result, '__await__'):  # Check if it's awaitable
            return await result
        return result
    
    async def poll_tickets(self):
        """Poll JIRA for new bug tickets"""
        try:
            logger.info("Polling JIRA for bug tickets...")
            tickets = await self.jira_client.fetch_bug_tickets()
            
            if not tickets:
                logger.info("No tickets found to process")
                return
                
            logger.info(f"Found {len(tickets)} tickets to process")
            for ticket in tickets:
                if not ticket:
                    logger.warning("Received empty ticket data, skipping")
                    continue
                    
                ticket_id = ticket.get("ticket_id")
                if not ticket_id:
                    logger.warning("Received ticket without ID, skipping")
                    continue
                    
                if ticket_id not in self.processed_tickets:
                    logger.info(f"Found new ticket to process: {ticket_id}")
                    await self.process_ticket(ticket)
        
        except Exception as e:
            logger.error(f"Error during ticket polling: {e}")
            logger.error(traceback.format_exc())
    
    async def start_polling(self):
        """Start the polling loop"""
        self.running = True
        logger.info(f"Starting JIRA polling loop every {self.poll_interval} seconds")
        
        while self.running:
            try:
                await self.poll_tickets()
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                logger.error(traceback.format_exc())
            
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
