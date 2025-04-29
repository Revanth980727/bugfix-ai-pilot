from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import importlib.util
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx

# Add the project root to the Python path
sys.path.append('/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("communicator-agent")

# Import github_utils directly - the file should be copied to the container
try:
    import github_utils
    create_branch = github_utils.create_branch
    commit_changes = github_utils.commit_changes
    create_pull_request = github_utils.create_pull_request
    logger.info("Successfully imported github_utils directly")
except ImportError as e:
    logger.error(f"Error importing github_utils directly: {str(e)}")
    # Fallback to old approach
    try:
        # Construct a path to github_utils.py that could be mounted in the Docker container
        path_options = [
            '/app/github_utils.py',  # Local copy
            '/app/backend/github_utils.py'  # Original path
        ]
        
        for path in path_options:
            if os.path.exists(path):
                logger.info(f"Found github_utils.py at {path}")
                
                # Create a module spec from the file path
                spec = importlib.util.spec_from_file_location("github_utils", path)
                github_utils = importlib.util.module_from_spec(spec)
                
                # Add an env module to the system modules to avoid import errors
                # This is a mock/stub for the env module
                sys.modules["env"] = type("env", (), {
                    "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN")
                })
                
                # Execute the module
                spec.loader.exec_module(github_utils)
                
                # Get the functions from the module
                create_branch = github_utils.create_branch
                commit_changes = github_utils.commit_changes
                create_pull_request = github_utils.create_pull_request
                
                break
        else:
            raise FileNotFoundError("Could not find github_utils.py")
    except Exception as e:
        logger.error(f"Error importing github_utils: {str(e)}")
        raise

app = FastAPI(title="BugFix AI Communicator Agent")

class FileDiff(BaseModel):
    filename: str
    diff: str
    lines_added: int
    lines_removed: int
    explanation: Optional[str] = None

class TestResult(BaseModel):
    name: str
    status: str
    duration: int
    output: Optional[str] = None
    error_message: Optional[str] = None

class DeployRequest(BaseModel):
    ticket_id: str
    diffs: List[FileDiff]
    test_results: List[TestResult]
    commit_message: str
    repository: str = "user/repo"  # Default value, should be overridden

class DeployResponse(BaseModel):
    ticket_id: str
    jira_status: str
    pr_url: Optional[str] = None
    timestamp: str = datetime.now().isoformat()

@app.get("/")
async def root():
    return {"message": "Communicator Agent is running", "status": "healthy"}

@app.post("/deploy", response_model=DeployResponse)
async def deploy_fix(request: DeployRequest):
    logger.info(f"Deploying fix for ticket {request.ticket_id}")
    
    try:
        # Create a branch for the fix
        branch_name = create_branch(
            request.repository,
            request.ticket_id,
            "main"  # Use main branch as base
        )
        
        if not branch_name:
            raise HTTPException(status_code=500, detail="Failed to create branch")
        
        # Format the diffs for the commit
        file_changes = []
        for diff in request.diffs:
            file_changes.append({
                "filename": diff.filename,
                "content": diff.diff
            })
        
        # Commit the changes
        commit_success = commit_changes(
            request.repository,
            branch_name,
            file_changes,
            request.commit_message
        )
        
        if not commit_success:
            raise HTTPException(status_code=500, detail="Failed to commit changes")
        
        # Create pull request
        pr_url = create_pull_request(
            request.repository,
            branch_name,
            request.ticket_id,
            f"Fix for {request.ticket_id}",
            f"Automated bug fix for {request.ticket_id}\n\nThis PR contains the following changes:\n" + 
            "\n".join([f"- {diff.filename}: {diff.explanation}" for diff in request.diffs])
        )
        
        # Update JIRA ticket status
        jira_success = await update_jira_ticket(request.ticket_id, pr_url)
        
        # Send notifications
        await send_notifications(request.ticket_id, pr_url, request.repository)
        
        logger.info(f"Deployment successful for ticket {request.ticket_id}, PR created at {pr_url}")
        
        return DeployResponse(
            ticket_id=request.ticket_id,
            jira_status="Ready for Review",
            pr_url=pr_url
        )
    
    except Exception as e:
        logger.error(f"Error deploying fix for ticket {request.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deploying fix: {str(e)}")

async def update_jira_ticket(ticket_id: str, pr_url: Optional[str] = None) -> bool:
    """Update the JIRA ticket with PR information"""
    try:
        # Get JIRA credentials from environment
        jira_token = os.environ.get("JIRA_TOKEN")
        jira_user = os.environ.get("JIRA_USER")
        jira_url = os.environ.get("JIRA_URL")
        
        if not all([jira_token, jira_user, jira_url]):
            logger.warning("JIRA credentials not fully configured, skipping ticket update")
            return False
        
        # Update JIRA ticket via the API
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Add comment with PR link
            comment_data = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": f"Bug fix implemented by BugFix AI. Pull request: {pr_url}"
                        }]
                    }]
                }
            }
            
            response = await client.post(
                f"{jira_url}/rest/api/3/issue/{ticket_id}/comment",
                json=comment_data,
                auth=(jira_user, jira_token)
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to add comment to JIRA: {response.status_code}")
                return False
            
            # Update ticket status
            transitions_response = await client.get(
                f"{jira_url}/rest/api/3/issue/{ticket_id}/transitions",
                auth=(jira_user, jira_token)
            )
            
            transitions = transitions_response.json().get("transitions", [])
            review_transition = next((t for t in transitions if "review" in t["name"].lower()), None)
            
            if review_transition:
                transition_data = {
                    "transition": {
                        "id": review_transition["id"]
                    }
                }
                
                transition_response = await client.post(
                    f"{jira_url}/rest/api/3/issue/{ticket_id}/transitions",
                    json=transition_data,
                    auth=(jira_user, jira_token)
                )
                
                if transition_response.status_code not in [200, 204]:
                    logger.error(f"Failed to update JIRA ticket status: {transition_response.status_code}")
                    return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error updating JIRA ticket {ticket_id}: {str(e)}")
        return False

async def send_notifications(ticket_id: str, pr_url: str, repository: str) -> None:
    """Send notifications about the fix via email and/or Slack"""
    try:
        # Check for email notification configuration
        email_host = os.environ.get("EMAIL_HOST")
        email_user = os.environ.get("EMAIL_USER")
        notification_email = os.environ.get("NOTIFICATION_EMAIL")
        
        if all([email_host, email_user, notification_email]):
            logger.info(f"Email notification would be sent for ticket {ticket_id}")
            # In a real implementation, this would send an email
            
        # Check for Slack notification configuration
        slack_token = os.environ.get("SLACK_TOKEN")
        slack_channel = os.environ.get("SLACK_CHANNEL")
        
        if all([slack_token, slack_channel]):
            logger.info(f"Slack notification would be sent for ticket {ticket_id}")
            # In a real implementation, this would send a Slack message
            
    except Exception as e:
        logger.error(f"Error sending notifications for ticket {ticket_id}: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8004, reload=True)
