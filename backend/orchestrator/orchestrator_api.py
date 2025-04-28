
from fastapi import FastAPI, HTTPException
import uvicorn
import asyncio
import json
from typing import Dict, Any
from pydantic import BaseModel
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.orchestrator import Orchestrator

app = FastAPI(title="BugFix AI Orchestrator API")

# Initialize orchestrator
orchestrator = Orchestrator()

# Start the background process
@app.on_event("startup")
async def startup_event():
    # Start orchestrator loop in background task
    asyncio.create_task(orchestrator.run_forever())


class TicketRequest(BaseModel):
    ticket_id: str
    title: str = ""
    description: str = ""


@app.get("/")
async def root():
    return {"message": "Orchestrator API is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": os.environ.get("VERSION", "development"),
        "services": {
            "orchestrator": "running",
            "agents": orchestrator.get_agent_statuses()
        }
    }


@app.get("/status")
async def get_status():
    """Get current status of the orchestrator"""
    return orchestrator.get_status()


@app.post("/process-ticket")
async def process_ticket(request: TicketRequest):
    """Manually trigger processing of a ticket"""
    # Convert to dict for processing
    ticket_dict = request.dict()
    
    # Check if ticket is already being processed
    if request.ticket_id in orchestrator.active_tickets:
        raise HTTPException(
            status_code=409, 
            detail=f"Ticket {request.ticket_id} is already being processed"
        )
    
    # Create task to process the ticket
    asyncio.create_task(orchestrator.process_ticket(ticket_dict))
    
    return {
        "message": f"Started processing ticket {request.ticket_id}",
        "status": "processing",
        "ticketId": request.ticket_id
    }


if __name__ == "__main__":
    uvicorn.run("orchestrator_api:app", host="0.0.0.0", port=8000, reload=True)
