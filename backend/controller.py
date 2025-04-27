
import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx
from pydantic import BaseModel

from env import JIRA_TOKEN, JIRA_USER, JIRA_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/controller_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bugfix-controller")

# Agent service URLs
PLANNER_URL = os.getenv("PLANNER_URL", "http://planner:8001")
DEVELOPER_URL = os.getenv("DEVELOPER_URL", "http://developer:8002")
QA_URL = os.getenv("QA_URL", "http://qa:8003")
COMMUNICATOR_URL = os.getenv("COMMUNICATOR_URL", "http://communicator:8004")

# Active tickets being processed
active_tickets = {}

class TicketRequest(BaseModel):
    ticket_id: str
    title: str
    description: str
    repository: str

class PlannerResponse(BaseModel):
    ticket_id: str
    affected_files: List[str]
    root_cause: str
    suggested_approach: str
    timestamp: str

class FileDiff(BaseModel):
    filename: str
    diff: str
    lines_added: int
    lines_removed: int

class DeveloperResponse(BaseModel):
    ticket_id: str
    diffs: List[FileDiff]
    commit_message: str
    timestamp: str
    attempt: int

class TestResult(BaseModel):
    name: str
    status: str  # "pass" or "fail"
    duration: int
    output: Optional[str] = None
    error_message: Optional[str] = None

class QAResponse(BaseModel):
    ticket_id: str
    passed: bool
    test_results: List[TestResult]
    timestamp: str

class Update(BaseModel):
    timestamp: str
    message: str
    type: str  # "jira", "github", or "system"

class DeployRequest(BaseModel):
    ticket_id: str
    repository: str
    branch_name: Optional[str] = None
    diffs: List[FileDiff]
    test_results: List[TestResult]
    commit_message: str

class DeployResponse(BaseModel):
    ticket_id: str
    pr_url: Optional[str] = None
    jira_url: Optional[str] = None
    updates: List[Update]
    timestamp: str
    success: bool

async def fetch_jira_tickets():
    """
    Poll the JIRA API for new tickets labeled as "Bug"
    """
    try:
        logger.info("Fetching new bug tickets from JIRA")
        auth = (JIRA_USER, JIRA_TOKEN)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # JQL query to find new bug tickets not yet in active_tickets
            jql_query = 'labels = Bug AND status = "To Do"'
            
            response = await client.get(
                f"{JIRA_URL}/rest/api/3/search",
                params={"jql": jql_query, "fields": "summary,description,created"},
                auth=auth
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch JIRA tickets: {response.status_code} - {response.text}")
                return []
                
            data = response.json()
            new_tickets = []
            
            for issue in data.get("issues", []):
                ticket_id = issue["key"]
                
                # Skip tickets already being processed
                if ticket_id in active_tickets:
                    continue
                    
                new_tickets.append({
                    "ticket_id": ticket_id,
                    "title": issue["fields"]["summary"],
                    "description": issue["fields"]["description"],
                    "created": issue["fields"]["created"]
                })
                
            logger.info(f"Found {len(new_tickets)} new bug tickets")
            return new_tickets
    except Exception as e:
        logger.error(f"Error fetching JIRA tickets: {str(e)}")
        return []

async def process_ticket(ticket: Dict[str, Any]):
    """Process a single ticket through the entire agent workflow"""
    ticket_id = ticket["ticket_id"]
    
    try:
        # Initialize ticket in active_tickets
        active_tickets[ticket_id] = {
            "ticket_id": ticket_id,
            "status": "processing",
            "started_at": datetime.now().isoformat(),
            "title": ticket["title"],
            "description": ticket["description"],
            "planner_analysis": None,
            "developer_diffs": None,
            "qa_results": None,
            "communicator_result": None,
            "current_attempt": 1,
            "max_attempts": 4
        }
        
        logger.info(f"Starting processing for ticket {ticket_id}")
        
        # Step 1: Send to Planner Agent
        logger.info(f"Sending ticket {ticket_id} to Planner agent")
        planner_analysis = await call_planner_agent(ticket)
        
        if not planner_analysis:
            logger.error(f"Failed to get analysis from Planner for ticket {ticket_id}")
            active_tickets[ticket_id]["status"] = "error"
            return
            
        active_tickets[ticket_id]["planner_analysis"] = planner_analysis
        
        # Step 2: Send to Developer Agent
        current_attempt = 1
        max_attempts = 4
        qa_passed = False
        
        while current_attempt <= max_attempts and not qa_passed:
            logger.info(f"Sending ticket {ticket_id} to Developer agent (attempt {current_attempt})")
            active_tickets[ticket_id]["current_attempt"] = current_attempt
            
            # Call Developer Agent
            developer_response = await call_developer_agent(planner_analysis, current_attempt)
            
            if not developer_response:
                logger.error(f"Failed to get response from Developer for ticket {ticket_id}")
                active_tickets[ticket_id]["status"] = "error"
                return
                
            active_tickets[ticket_id]["developer_diffs"] = developer_response
            
            # Step 3: Apply Developer's patch
            await apply_code_changes(developer_response)
            
            # Step 4: Send to QA Agent
            logger.info(f"Sending ticket {ticket_id} to QA agent (attempt {current_attempt})")
            qa_response = await call_qa_agent(developer_response)
            
            if not qa_response:
                logger.error(f"Failed to get response from QA for ticket {ticket_id}")
                active_tickets[ticket_id]["status"] = "error"
                return
                
            active_tickets[ticket_id]["qa_results"] = qa_response
            
            # Check if QA passed
            qa_passed = qa_response.passed
            
            if qa_passed:
                logger.info(f"QA tests passed for ticket {ticket_id} on attempt {current_attempt}")
                break
                
            logger.info(f"QA tests failed for ticket {ticket_id} on attempt {current_attempt}")
            current_attempt += 1
            
        # Step 5: Send to Communicator Agent
        logger.info(f"Sending ticket {ticket_id} to Communicator agent")
        
        communicator_response = await call_communicator_agent(
            ticket_id,
            developer_response.diffs,
            qa_response.test_results,
            developer_response.commit_message
        )
        
        if communicator_response:
            active_tickets[ticket_id]["communicator_result"] = communicator_response
            active_tickets[ticket_id]["status"] = "completed"
            logger.info(f"Completed processing for ticket {ticket_id}")
        else:
            logger.error(f"Failed to get response from Communicator for ticket {ticket_id}")
            active_tickets[ticket_id]["status"] = "error"
            
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
        active_tickets[ticket_id]["status"] = "error"
        active_tickets[ticket_id]["error"] = str(e)

async def call_planner_agent(ticket: Dict[str, Any]) -> Optional[PlannerResponse]:
    """Send ticket information to the Planner agent"""
    try:
        ticket_request = TicketRequest(
            ticket_id=ticket["ticket_id"],
            title=ticket["title"],
            description=ticket["description"],
            repository="main"  # This would be configurable in a real implementation
        )
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{PLANNER_URL}/analyze",
                json=ticket_request.dict()
            )
            
            if response.status_code != 200:
                logger.error(f"Planner agent error: {response.status_code} - {response.text}")
                return None
                
            return PlannerResponse(**response.json())
    except Exception as e:
        logger.error(f"Error calling Planner agent: {str(e)}")
        return None

async def call_developer_agent(planner_analysis: PlannerResponse, attempt: int) -> Optional[DeveloperResponse]:
    """Send Planner's output to Developer agent"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:  # Longer timeout for code generation
            response = await client.post(
                f"{DEVELOPER_URL}/generate-fix",
                json={
                    "ticket_id": planner_analysis.ticket_id,
                    "affected_files": planner_analysis.affected_files,
                    "root_cause": planner_analysis.root_cause,
                    "suggested_approach": planner_analysis.suggested_approach,
                    "attempt": attempt
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Developer agent error: {response.status_code} - {response.text}")
                return None
                
            return DeveloperResponse(**response.json())
    except Exception as e:
        logger.error(f"Error calling Developer agent: {str(e)}")
        return None

async def apply_code_changes(developer_response: DeveloperResponse) -> bool:
    """Apply the Developer's patch to the mounted repository"""
    try:
        # In a real implementation, this would apply the diffs to the actual files
        # For now, we'll just log the changes
        logger.info(f"Applying code changes for ticket {developer_response.ticket_id}")
        
        for diff in developer_response.diffs:
            logger.info(f"Applying diff to file: {diff.filename}")
            # In production, we would write these changes to the actual files
            
        return True
    except Exception as e:
        logger.error(f"Error applying code changes: {str(e)}")
        return False

async def call_qa_agent(developer_response: DeveloperResponse) -> Optional[QAResponse]:
    """Send Developer's patch to QA agent"""
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{QA_URL}/test-fix",
                json=developer_response.dict()
            )
            
            if response.status_code != 200:
                logger.error(f"QA agent error: {response.status_code} - {response.text}")
                return None
                
            return QAResponse(**response.json())
    except Exception as e:
        logger.error(f"Error calling QA agent: {str(e)}")
        return None

async def call_communicator_agent(
    ticket_id: str,
    diffs: List[FileDiff],
    test_results: List[TestResult],
    commit_message: str
) -> Optional[DeployResponse]:
    """Send results to Communicator agent"""
    try:
        deploy_request = DeployRequest(
            ticket_id=ticket_id,
            repository="main",  # This would be configurable in a real implementation
            diffs=diffs,
            test_results=test_results,
            commit_message=commit_message
        )
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{COMMUNICATOR_URL}/deploy",
                json=deploy_request.dict()
            )
            
            if response.status_code != 200:
                logger.error(f"Communicator agent error: {response.status_code} - {response.text}")
                return None
                
            return DeployResponse(**response.json())
    except Exception as e:
        logger.error(f"Error calling Communicator agent: {str(e)}")
        return None

async def run_controller():
    """Main controller loop that runs every 60 seconds"""
    while True:
        try:
            # Fetch new tickets from JIRA
            new_tickets = await fetch_jira_tickets()
            
            # Process each new ticket
            for ticket in new_tickets:
                # Start processing in the background
                asyncio.create_task(process_ticket(ticket))
                
            # Clean up old completed tickets from memory after 1 hour
            current_time = datetime.now()
            tickets_to_remove = []
            
            for ticket_id, ticket_data in active_tickets.items():
                if ticket_data["status"] in ["completed", "error"]:
                    started_at = datetime.fromisoformat(ticket_data["started_at"])
                    if (current_time - started_at).total_seconds() > 3600:  # 1 hour
                        tickets_to_remove.append(ticket_id)
                        
            for ticket_id in tickets_to_remove:
                del active_tickets[ticket_id]
                
            # Wait for 60 seconds before the next polling cycle
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Controller error: {str(e)}")
            await asyncio.sleep(60)  # Still wait before retrying

def start_controller():
    """Start the controller loop"""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_controller())
    except KeyboardInterrupt:
        logger.info("Controller stopping due to keyboard interrupt")
    finally:
        loop.close()

if __name__ == "__main__":
    start_controller()
