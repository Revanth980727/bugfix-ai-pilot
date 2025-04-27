
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("planner-agent")

app = FastAPI(title="BugFix AI Planner Agent")

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
    timestamp: str = datetime.now().isoformat()

@app.get("/")
async def root():
    return {"message": "Planner Agent is running", "status": "healthy"}

@app.post("/analyze", response_model=PlannerResponse)
async def analyze_ticket(request: TicketRequest):
    logger.info(f"Analyzing ticket {request.ticket_id}: {request.title}")
    
    try:
        # In a real implementation, this would use OpenAI to analyze the ticket
        # For now, we'll return mock data
        
        # Simulated analysis result
        response = PlannerResponse(
            ticket_id=request.ticket_id,
            affected_files=[
                "src/components/auth/login.js",
                "src/api/userService.js",
                "src/utils/validation.js"
            ],
            root_cause="The login functionality fails when special characters are used in passwords because the validation function does not properly handle these cases.",
            suggested_approach="Update the validation function to correctly handle special characters in passwords and ensure consistent validation between frontend and backend."
        )
        
        logger.info(f"Analysis completed for ticket {request.ticket_id}")
        return response
    
    except Exception as e:
        logger.error(f"Error analyzing ticket {request.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing ticket: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8001, reload=True)
