from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import os
from datetime import datetime
from env import verify_env_vars, GITHUB_TOKEN, JIRA_TOKEN, JIRA_USER, JIRA_URL

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

class TicketRequest(BaseModel):
    ticket_id: str
    jira_instance: str = "cloud"  # or "server"

class AgentStatus(BaseModel):
    agent_id: str
    status: str
    progress: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = datetime.now().isoformat()

# Store active tickets and their status
active_tickets = {}

@app.get("/")
async def root():
    return {
        "message": "BugFix AI Pilot API is running",
        "github_configured": bool(GITHUB_TOKEN),
        "jira_configured": all([JIRA_TOKEN, JIRA_USER, JIRA_URL])
    }

@app.post("/tickets/process")
async def process_ticket(request: TicketRequest):
    ticket_id = request.ticket_id
    
    # Check if ticket is already being processed
    if ticket_id in active_tickets:
        return {"message": f"Ticket {ticket_id} is already being processed", "status": active_tickets[ticket_id]}
    
    # Initialize ticket processing status
    active_tickets[ticket_id] = {
        "ticket_id": ticket_id,
        "jira_instance": request.jira_instance,
        "status": "initializing",
        "started_at": datetime.now().isoformat(),
        "agents": {
            "planner": {"status": "pending", "progress": 0},
            "developer": {"status": "pending", "progress": 0},
            "qa": {"status": "pending", "progress": 0},
            "communicator": {"status": "pending", "progress": 0}
        },
        "current_attempt": 0,
        "max_attempts": 4
    }
    
    logger.info(f"Started processing ticket {ticket_id}")
    
    # In a real implementation, this would trigger the agent workflow
    # Instead, we'll just return the initial status
    return {"message": f"Started processing ticket {ticket_id}", "status": active_tickets[ticket_id]}

@app.get("/tickets/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    if ticket_id not in active_tickets:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return active_tickets[ticket_id]

@app.get("/tickets")
async def list_active_tickets():
    return list(active_tickets.values())

@app.post("/agents/{agent_id}/update")
async def update_agent_status(agent_id: str, status: AgentStatus):
    ticket_id = status.details.get("ticket_id") if status.details else None
    if not ticket_id or ticket_id not in active_tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Update agent status
    active_tickets[ticket_id]["agents"][agent_id] = {
        "status": status.status,
        "progress": status.progress,
        "details": status.details,
        "updated_at": status.timestamp
    }
    
    logger.info(f"Updated {agent_id} status for ticket {ticket_id}: {status.status}")
    
    return {"message": f"Updated {agent_id} status for ticket {ticket_id}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
