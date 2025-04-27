
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("communicator-agent")

app = FastAPI(title="BugFix AI Communicator Agent")

class FileDiff(BaseModel):
    filename: str
    diff: str
    lines_added: int
    lines_removed: int

class TestResult(BaseModel):
    name: str
    status: Literal["pass", "fail"]
    duration: int
    output: Optional[str] = None
    error_message: Optional[str] = None

class QAResponse(BaseModel):
    ticket_id: str
    passed: bool
    test_results: List[TestResult]

class DeployRequest(BaseModel):
    ticket_id: str
    repository: str
    branch_name: Optional[str] = None
    diffs: List[FileDiff]
    test_results: List[TestResult]
    commit_message: str

class Update(BaseModel):
    timestamp: str
    message: str
    type: Literal["jira", "github", "system"]

class DeployResponse(BaseModel):
    ticket_id: str
    pr_url: Optional[str] = None
    jira_url: Optional[str] = None
    updates: List[Update]
    timestamp: str = datetime.now().isoformat()
    success: bool

@app.get("/")
async def root():
    return {"message": "Communicator Agent is running", "status": "healthy"}

@app.post("/deploy", response_model=DeployResponse)
async def deploy_fix(request: DeployRequest):
    logger.info(f"Deploying fix for ticket {request.ticket_id}")
    
    try:
        # In a real implementation, this would create a PR and update JIRA
        # For now, we'll return mock data
        
        # Simulated deployment process
        updates = [
            Update(
                timestamp=datetime.now().isoformat(),
                message="Starting deployment process",
                type="system"
            ),
            Update(
                timestamp=datetime.now().isoformat(),
                message=f"Creating branch bugfix/{request.ticket_id}",
                type="github"
            ),
            Update(
                timestamp=datetime.now().isoformat(),
                message=f"Committing changes: {request.commit_message}",
                type="github"
            ),
            Update(
                timestamp=datetime.now().isoformat(),
                message=f"Creating pull request for {request.ticket_id}",
                type="github"
            ),
            Update(
                timestamp=datetime.now().isoformat(),
                message=f"Updating JIRA ticket {request.ticket_id} with PR link and test results",
                type="jira"
            ),
            Update(
                timestamp=datetime.now().isoformat(),
                message="Deployment completed successfully",
                type="system"
            )
        ]
        
        response = DeployResponse(
            ticket_id=request.ticket_id,
            pr_url=f"https://github.com/org/repo/pull/45",
            jira_url=f"https://jira.company.com/browse/{request.ticket_id}",
            updates=updates,
            success=True
        )
        
        logger.info(f"Deployment completed for ticket {request.ticket_id}")
        return response
    
    except Exception as e:
        logger.error(f"Error deploying fix for ticket {request.ticket_id}: {str(e)}")
        
        # Return error response with updates about the failure
        error_updates = [
            Update(
                timestamp=datetime.now().isoformat(),
                message="Starting deployment process",
                type="system"
            ),
            Update(
                timestamp=datetime.now().isoformat(),
                message=f"Error: {str(e)}",
                type="system"
            )
        ]
        
        return DeployResponse(
            ticket_id=request.ticket_id,
            updates=error_updates,
            success=False
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8004, reload=True)
