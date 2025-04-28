
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
RETRY_DELAY_SECONDS = 5  # Delay between retries


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
            "escalated": False,
            "retry_history": []  # Store retry history with QA errors
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
        
        # Initialize retry history for this ticket
        retry_history = []
        
        while current_attempt <= max_retries and not success:
            logger.info(f"Starting development attempt {current_attempt}/{max_retries} for ticket {ticket_id}")
            
            # Update ticket tracking
            self.active_tickets[ticket_id]["current_attempt"] = current_attempt
            
            try:
                # STEP 2: Run developer agent
                logger.info(f"Running DeveloperAgent for ticket {ticket_id} (attempt {current_attempt})")
                
                # Add context for retries with previous QA failures
                developer_context = {"previousAttempts": retry_history}
                
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
                
                # Log the retry status with enhanced failure information
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                result_status = "PASS" if success else "FAIL"
                
                failure_info = ""
                if not success and "failure_summary" in qa_result:
                    failure_info = f" | Failure: {qa_result['failure_summary'].replace(chr(10), ' ')}"
                    
                log_message = f"[Ticket: {ticket_id}] Retry {current_attempt}/{max_retries} | QA Result: {result_status}{failure_info} | {timestamp}"
                logger.info(log_message)
                
                # Store the QA results in retry history for future attempts
                retry_entry = {
                    "attempt": current_attempt,
                    "patch_content": developer_result.get("patch_content", ""),
                    "qa_results": qa_result
                }
                
                retry_history.append(retry_entry)
                self.active_tickets[ticket_id]["retry_history"] = retry_history
                
                if success:
                    logger.info(f"QA tests passed for ticket {ticket_id} on attempt {current_attempt}")
                    
                    # Clear the QA failure history since we succeeded
                    retry_history = []
                    self.active_tickets[ticket_id]["retry_history"] = []
                    
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
                        break  # Exit retry loop after escalation
                    else:
                        # Update JIRA with retry information and failure summary
                        failure_summary = qa_result.get("failure_summary", "Unknown failure")
                        await self.jira_client.update_ticket(
                            ticket_id,
                            "In Progress",
                            f"Attempt {current_attempt}/{max_retries} failed with errors: {failure_summary}. Retrying with improved fix..."
                        )
                        
                        # Add delay between retries to avoid hammering the system
                        logger.info(f"Waiting {RETRY_DELAY_SECONDS} seconds before next retry")
                        await asyncio.sleep(RETRY_DELAY_SECONDS)
            
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
                else:
                    # Record error in retry history
                    retry_entry = {
                        "attempt": current_attempt,
                        "error": str(e)
                    }
                    retry_history.append(retry_entry)
                    
                    # Add delay between retries
                    logger.info(f"Waiting {RETRY_DELAY_SECONDS} seconds before next retry")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
            
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
            # Mark ticket as escalated
            self.active_tickets[ticket_id]["status"] = "escalated"
            self.active_tickets[ticket_id]["escalated"] = True
            
            # Extract failure summary for more informative escalation
            failure_summary = qa_result.get("failure_summary", "")
            if not failure_summary and "error" in qa_result:
                failure_summary = qa_result["error"]
            
            # Run communicator agent for escalation
            logger.info(f"Running CommunicatorAgent for escalation of ticket {ticket_id}")
            
            communicator_input = {
                "ticket_id": ticket_id,
                "test_passed": False,
                "github_pr_url": None,
                "retry_count": attempt,
                "max_retries": MAX_RETRIES,
                "escalated": True,
                "failure_summary": failure_summary
            }
            
            log_dir = f"logs/{ticket_id}"
            with open(f"{log_dir}/communicator_input_escalation.json", 'w') as f:
                json.dump(communicator_input, f, indent=2)
            
            communicator_result = await self.run_agent(self.communicator_agent, communicator_input)
            
            with open(f"{log_dir}/communicator_output_escalation.json", 'w') as f:
                json.dump(communicator_result, f, indent=2)
            
            # Update JIRA ticket with escalation message including failure summary
            escalation_message = f"Automatic retry limit ({MAX_RETRIES}) reached. Last failure: {failure_summary}"
            await self.jira_client.update_ticket(
                ticket_id,
                "Needs Review",
                escalation_message
            )
            
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
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the orchestrator"""
        return {
            "active_tickets": len(self.active_tickets),
            "tickets": self.active_tickets
        }
    
    def get_agent_statuses(self) -> Dict[str, str]:
        """Get statuses of all agents for health check"""
        return {
            "planner": "ready",
            "developer": "ready",
            "qa": "ready",
            "communicator": "ready"
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
