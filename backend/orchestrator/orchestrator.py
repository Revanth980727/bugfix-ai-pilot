
import asyncio
import logging
import os
import json
from datetime import datetime
import traceback
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import agent frameworks
from ..agent_framework.planner_agent import PlannerAgent
from ..agent_framework.developer_agent import DeveloperAgent
from ..agent_framework.qa_agent import QAAgent 
from ..agent_framework.communicator_agent import CommunicatorAgent
from ..jira_service.jira_client import JiraClient
from ..github_service.github_service import GitHubService
from ..env import MAX_RETRIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/orchestrator_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("orchestrator")

# Constants and config
POLL_INTERVAL_SECONDS = int(os.environ.get('POLL_INTERVAL_SECONDS', '60'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '4'))
REPO_PATH = os.environ.get('REPO_PATH', '/app/code_repo')


class Orchestrator:
    def __init__(self):
        """Initialize orchestrator and its dependencies"""
        self.jira_client = JiraClient()
        self.github_service = GitHubService()
        
        # Initialize agent instances
        self.planner_agent = PlannerAgent()
        self.developer_agent = DeveloperAgent()
        self.qa_agent = QAAgent()
        self.communicator_agent = CommunicatorAgent()
        
        # Track active tickets
        self.active_tickets = {}
        
        logger.info("Orchestrator initialized")
    
    async def fetch_eligible_tickets(self) -> List[Dict[str, Any]]:
        """Fetch eligible tickets from JIRA that need processing"""
        try:
            # This should be replaced with actual JIRA API call
            tickets = await self.jira_client.get_open_bugs()
            
            # Filter out tickets already being processed
            eligible_tickets = [
                t for t in tickets 
                if t["ticket_id"] not in self.active_tickets
            ]
            
            if eligible_tickets:
                logger.info(f"Found {len(eligible_tickets)} eligible tickets for processing")
            
            return eligible_tickets
        except Exception as e:
            logger.error(f"Error fetching eligible tickets: {str(e)}")
            return []
    
    async def process_ticket(self, ticket: Dict[str, Any]) -> None:
        """Process a single ticket through the AI agent pipeline"""
        ticket_id = ticket["ticket_id"]
        
        # Mark ticket as being processed
        self.active_tickets[ticket_id] = {
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "current_attempt": 0,
        }
        
        logger.info(f"Starting processing for ticket {ticket_id}")
        
        # Create log directory for this ticket
        log_dir = f"logs/{ticket_id}"
        os.makedirs(log_dir, exist_ok=True)
        
        try:
            # STEP 1: Run planner agent
            logger.info(f"Running PlannerAgent for ticket {ticket_id}")
            
            planner_input = {
                "ticket_id": ticket_id,
                "title": ticket.get("title", ""),
                "description": ticket.get("description", ""),
            }
            
            with open(f"{log_dir}/planner_input.json", 'w') as f:
                json.dump(planner_input, f, indent=2)
            
            planner_result = await self.run_agent(self.planner_agent, planner_input)
            
            if not planner_result or "error" in planner_result:
                raise Exception(f"PlannerAgent failed: {planner_result.get('error', 'Unknown error')}")
            
            with open(f"{log_dir}/planner_output.json", 'w') as f:
                json.dump(planner_result, f, indent=2)
            
            # Update ticket status
            self.active_tickets[ticket_id]["planner_result"] = planner_result
            
            # STEP 2-4: Developer-QA loop with retries
            await self.run_development_qa_loop(ticket_id, planner_result)
            
        except Exception as e:
            logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update ticket as failed
            self.active_tickets[ticket_id]["status"] = "failed"
            self.active_tickets[ticket_id]["error"] = str(e)
            
            # Try to update JIRA with the failure
            try:
                await self.jira_client.update_ticket(
                    ticket_id, 
                    "Needs Review", 
                    f"Automatic bug fix process failed with error: {str(e)}"
                )
            except Exception as jira_error:
                logger.error(f"Failed to update JIRA for ticket {ticket_id}: {str(jira_error)}")
    
    async def run_development_qa_loop(self, ticket_id: str, planner_result: Dict[str, Any]) -> None:
        """Run the developer-QA loop with retries"""
        max_retries = MAX_RETRIES
        current_attempt = 1
        success = False
        
        log_dir = f"logs/{ticket_id}"
        
        while current_attempt <= max_retries and not success:
            logger.info(f"Starting development attempt {current_attempt}/{max_retries} for ticket {ticket_id}")
            
            # Update ticket tracking
            self.active_tickets[ticket_id]["current_attempt"] = current_attempt
            
            try:
                # STEP 2: Run developer agent
                logger.info(f"Running DeveloperAgent for ticket {ticket_id} (attempt {current_attempt})")
                
                # Add context for retries
                developer_context = {"previousAttempts": []}
                if current_attempt > 1 and "qa_result" in self.active_tickets[ticket_id]:
                    developer_context["previousAttempts"].append({
                        "attempt": current_attempt - 1,
                        "qaResults": self.active_tickets[ticket_id]["qa_result"]
                    })
                
                developer_input = {
                    "ticket_id": ticket_id,
                    **planner_result,
                    "attempt": current_attempt,
                    "max_attempts": max_retries,
                    "context": developer_context
                }
                
                with open(f"{log_dir}/developer_input_{current_attempt}.json", 'w') as f:
                    json.dump(developer_input, f, indent=2)
                
                developer_result = await self.run_agent(self.developer_agent, developer_input)
                
                if not developer_result or "error" in developer_result:
                    raise Exception(f"DeveloperAgent failed: {developer_result.get('error', 'Unknown error')}")
                
                with open(f"{log_dir}/developer_output_{current_attempt}.json", 'w') as f:
                    json.dump(developer_result, f, indent=2)
                
                # Update ticket tracking
                self.active_tickets[ticket_id]["developer_result"] = developer_result
                
                # STEP 3: Run QA agent
                logger.info(f"Running QAAgent for ticket {ticket_id} (attempt {current_attempt})")
                
                qa_input = {
                    "ticket_id": ticket_id,
                    "test_command": "npm test",  # Default test command, could be customized
                }
                
                with open(f"{log_dir}/qa_input_{current_attempt}.json", 'w') as f:
                    json.dump(qa_input, f, indent=2)
                
                qa_result = await self.run_agent(self.qa_agent, qa_input)
                
                if not qa_result:
                    raise Exception(f"QAAgent failed with no result")
                
                with open(f"{log_dir}/qa_output_{current_attempt}.json", 'w') as f:
                    json.dump(qa_result, f, indent=2)
                
                # Update ticket tracking
                self.active_tickets[ticket_id]["qa_result"] = qa_result
                
                # Check if tests passed
                success = qa_result.get("passed", False)
                
                if success:
                    logger.info(f"QA tests passed for ticket {ticket_id} on attempt {current_attempt}")
                    
                    # STEP 4: Create PR and update JIRA via communicator agent
                    await self.finalize_successful_fix(
                        ticket_id, 
                        current_attempt, 
                        developer_result, 
                        qa_result
                    )
                else:
                    logger.warning(f"QA tests failed for ticket {ticket_id} on attempt {current_attempt}")
                    
                    # Try again or escalate
                    if current_attempt >= max_retries:
                        logger.warning(f"Maximum retries reached for ticket {ticket_id}, escalating")
                        await self.escalate_ticket(ticket_id, current_attempt, qa_result)
                    else:
                        # Update JIRA with retry information
                        await self.jira_client.update_ticket(
                            ticket_id,
                            "In Progress",
                            f"Attempt {current_attempt}/{max_retries} failed. Retrying fix generation..."
                        )
            
            except Exception as e:
                logger.error(f"Error in development-QA loop for ticket {ticket_id}: {str(e)}")
                
                # If we've used all retries or it's a non-fixable error, escalate
                if current_attempt >= max_retries:
                    await self.escalate_ticket(
                        ticket_id, 
                        current_attempt, 
                        {"error": str(e), "passed": False}
                    )
                    break
            
            current_attempt += 1
    
    async def finalize_successful_fix(
        self, 
        ticket_id: str, 
        attempt: int,
        developer_result: Dict[str, Any],
        qa_result: Dict[str, Any]
    ) -> None:
        """Finalize a successful fix by creating PR and updating JIRA"""
        try:
            # In a real implementation, would create a PR here
            # For now, just simulate it with a fake URL
            pr_url = f"https://github.com/org/repo/pull/{ticket_id}"
            
            # Run communicator agent
            logger.info(f"Running CommunicatorAgent for successful fix of ticket {ticket_id}")
            
            communicator_input = {
                "ticket_id": ticket_id,
                "test_passed": True,
                "github_pr_url": pr_url,
                "retry_count": attempt,
                "max_retries": MAX_RETRIES
            }
            
            log_dir = f"logs/{ticket_id}"
            with open(f"{log_dir}/communicator_input.json", 'w') as f:
                json.dump(communicator_input, f, indent=2)
            
            communicator_result = await self.run_agent(self.communicator_agent, communicator_input)
            
            with open(f"{log_dir}/communicator_output.json", 'w') as f:
                json.dump(communicator_result, f, indent=2)
            
            # Update ticket tracking
            self.active_tickets[ticket_id]["status"] = "completed"
            self.active_tickets[ticket_id]["pr_url"] = pr_url
            
            logger.info(f"Successfully completed fix for ticket {ticket_id}")
            
        except Exception as e:
            logger.error(f"Error finalizing successful fix for ticket {ticket_id}: {str(e)}")
            # Even if PR creation fails, we still have the fix locally
            # Mark as needing review
            await self.jira_client.update_ticket(
                ticket_id,
                "Needs Review",
                f"Fix was generated successfully but PR creation failed: {str(e)}"
            )
    
    async def escalate_ticket(
        self, 
        ticket_id: str, 
        attempt: int, 
        qa_result: Dict[str, Any]
    ) -> None:
        """Escalate a ticket after failed attempts"""
        try:
            # Run communicator agent for escalation
            logger.info(f"Running CommunicatorAgent for escalation of ticket {ticket_id}")
            
            communicator_input = {
                "ticket_id": ticket_id,
                "test_passed": False,
                "github_pr_url": None,
                "retry_count": attempt,
                "max_retries": MAX_RETRIES
            }
            
            log_dir = f"logs/{ticket_id}"
            with open(f"{log_dir}/communicator_input_escalation.json", 'w') as f:
                json.dump(communicator_input, f, indent=2)
            
            communicator_result = await self.run_agent(self.communicator_agent, communicator_input)
            
            with open(f"{log_dir}/communicator_output_escalation.json", 'w') as f:
                json.dump(communicator_result, f, indent=2)
            
            # Update ticket tracking
            self.active_tickets[ticket_id]["status"] = "escalated"
            
            logger.info(f"Ticket {ticket_id} has been escalated after {attempt} failed attempts")
            
        except Exception as e:
            logger.error(f"Error escalating ticket {ticket_id}: {str(e)}")
    
    async def run_agent(self, agent: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run an agent with error handling and retry logic"""
        try:
            result = await asyncio.to_thread(agent.process, input_data)
            return result
        except Exception as e:
            logger.error(f"Error running {agent.name}: {str(e)}")
            return {"error": str(e)}
    
    async def cleanup_completed_tickets(self, age_hours: int = 24) -> None:
        """Clean up completed tickets from memory after specified age"""
        current_time = datetime.now()
        tickets_to_remove = []
        
        for ticket_id, data in self.active_tickets.items():
            if data["status"] in ["completed", "escalated", "failed"]:
                start_time = datetime.fromisoformat(data["start_time"])
                age = (current_time - start_time).total_seconds() / 3600  # hours
                
                if age > age_hours:
                    tickets_to_remove.append(ticket_id)
        
        for ticket_id in tickets_to_remove:
            del self.active_tickets[ticket_id]
            logger.info(f"Removed completed ticket {ticket_id} from active tracking")
    
    async def run_forever(self) -> None:
        """Run the orchestrator in an infinite loop"""
        logger.info("Starting orchestrator main loop")
        
        while True:
            try:
                # Get tickets to process
                tickets = await self.fetch_eligible_tickets()
                
                # Process each ticket
                for ticket in tickets:
                    asyncio.create_task(self.process_ticket(ticket))
                
                # Clean up old completed tickets
                await self.cleanup_completed_tickets()
                
                # Wait before next poll
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                
            except Exception as e:
                logger.error(f"Error in orchestrator main loop: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Wait before retry
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the orchestrator"""
        return {
            "active_tickets": len(self.active_tickets),
            "tickets": self.active_tickets
        }


async def start_orchestrator():
    """Initialize and start the orchestrator"""
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    orchestrator = Orchestrator()
    await orchestrator.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(start_orchestrator())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")
