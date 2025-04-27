
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import os
from datetime import datetime
import httpx
import asyncio
from env import verify_env_vars, GITHUB_TOKEN, JIRA_TOKEN, JIRA_USER, JIRA_URL
import controller

# Verify environment variables on startup
verify_env_vars()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/bugfix_ai_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("bugfix-ai")

app = FastAPI(title="BugFix AI Pilot")

# Agent service URLs
PLANNER_URL = os.getenv("PLANNER_URL", "http://planner:8001")
DEVELOPER_URL = os.getenv("DEVELOPER_URL", "http://developer:8002")
QA_URL = os.getenv("QA_URL", "http://qa:8003")
COMMUNICATOR_URL = os.getenv("COMMUNICATOR_URL", "http://communicator:8004")

class TicketRequest(BaseModel):
    ticket_id: str
    jira_instance: str = "cloud"  # or "server"

class AgentStatus(BaseModel):
    agent_id: str
    status: str
    progress: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = datetime.now().isoformat()

@app.get("/")
async def root():
    return {
        "message": "BugFix AI Pilot API is running",
        "github_configured": bool(GITHUB_TOKEN),
        "jira_configured": all([JIRA_TOKEN, JIRA_USER, JIRA_URL])
    }

@app.post("/tickets/process")
async def process_ticket(request: TicketRequest, background_tasks: BackgroundTasks):
    ticket_id = request.ticket_id
    
    # Check if ticket is already being processed
    if ticket_id in controller.active_tickets:
        return {"message": f"Ticket {ticket_id} is already being processed", "status": controller.active_tickets[ticket_id]}
    
    # Get ticket details from JIRA
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth = (JIRA_USER, JIRA_TOKEN)
            response = await client.get(
                f"{JIRA_URL}/rest/api/3/issue/{ticket_id}",
                params={"fields": "summary,description,created"},
                auth=auth
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found in JIRA")
                
            issue = response.json()
            ticket = {
                "ticket_id": ticket_id,
                "title": issue["fields"]["summary"],
                "description": issue["fields"]["description"],
                "created": issue["fields"]["created"]
            }
    except Exception as e:
        logger.error(f"Error fetching ticket {ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching ticket: {str(e)}")
    
    # Start processing in the background
    background_tasks.add_task(controller.process_ticket, ticket)
    
    # Return initial status
    return {"message": f"Started processing ticket {ticket_id}", "status": "initializing"}

@app.get("/tickets/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    if ticket_id not in controller.active_tickets:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return controller.active_tickets[ticket_id]

@app.get("/tickets")
async def list_active_tickets():
    return list(controller.active_tickets.values())

@app.post("/agents/{agent_id}/update")
async def update_agent_status(agent_id: str, status: AgentStatus):
    ticket_id = status.details.get("ticket_id") if status.details else None
    if not ticket_id or ticket_id not in controller.active_tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Update agent status
    controller.active_tickets[ticket_id]["agents"] = controller.active_tickets[ticket_id].get("agents", {})
    controller.active_tickets[ticket_id]["agents"][agent_id] = {
        "status": status.status,
        "progress": status.progress,
        "details": status.details,
        "updated_at": status.timestamp
    }
    
    logger.info(f"Updated {agent_id} status for ticket {ticket_id}: {status.status}")
    
    return {"message": f"Updated {agent_id} status for ticket {ticket_id}"}

@app.get("/agents/health")
async def check_agents_health():
    """Check the health of all agent services."""
    health = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for agent, url in [
            ("planner", PLANNER_URL),
            ("developer", DEVELOPER_URL),
            ("qa", QA_URL),
            ("communicator", COMMUNICATOR_URL)
        ]:
            try:
                response = await client.get(f"{url}/")
                health[agent] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "details": response.json() if response.status_code == 200 else None
                }
            except Exception as e:
                health[agent] = {"status": "error", "message": str(e)}
    
    return health

@app.on_event("startup")
async def startup_event():
    # Start the controller in a background task
    asyncio.create_task(controller.run_controller())
    logger.info("Controller started and running in background")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
