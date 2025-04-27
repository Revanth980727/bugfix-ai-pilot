
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
import httpx
from jira import JIRA
import asyncio
import sys

# Add the backend directory to path to import utilities
sys.path.insert(0, '/app/backend')
try:
    from github_utils import create_branch, commit_changes, create_pull_request
except ImportError:
    # For local development when not in Docker
    import importlib.util
    spec = importlib.util.spec_from_file_location("github_utils", "../backend/github_utils.py")
    github_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(github_utils)
    create_branch = github_utils.create_branch
    commit_changes = github_utils.commit_changes
    create_pull_request = github_utils.create_pull_request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("communicator-agent")

# Get environment variables
JIRA_TOKEN = os.getenv('JIRA_TOKEN')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_URL = os.getenv('JIRA_URL')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

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

async def update_jira_ticket(ticket_id: str, status: str, comment: str, pr_url: Optional[str] = None) -> bool:
    """Update a JIRA ticket status and add a comment"""
    try:
        # Initialize JIRA client
        auth = (JIRA_USER, JIRA_TOKEN)
        jira_instance = JIRA(server=JIRA_URL, basic_auth=auth)
        
        # Add comment
        jira_instance.add_comment(ticket_id, comment)
        
        # Update status if needed
        if status:
            # Get available transitions
            transitions = jira_instance.transitions(ticket_id)
            transition_id = None
            
            for t in transitions:
                if status.lower() in t['name'].lower():
                    transition_id = t['id']
                    break
            
            if transition_id:
                jira_instance.transition_issue(ticket_id, transition_id)
        
        # Add PR link as a remote link if provided
        if pr_url:
            jira_instance.add_simple_link(ticket_id, {
                'url': pr_url,
                'title': 'GitHub Pull Request'
            })
        
        return True
    except Exception as e:
        logger.error(f"Error updating JIRA ticket {ticket_id}: {str(e)}")
        return False

@app.get("/")
async def root():
    return {
        "message": "Communicator Agent is running", 
        "status": "healthy", 
        "jira_configured": all([JIRA_TOKEN, JIRA_USER, JIRA_URL]),
        "github_configured": bool(GITHUB_TOKEN)
    }

@app.post("/deploy", response_model=DeployResponse)
async def deploy_fix(request: DeployRequest):
    logger.info(f"Deploying fix for ticket {request.ticket_id}")
    
    updates = []
    success = True
    pr_url = None
    jira_url = f"{JIRA_URL}/browse/{request.ticket_id}" if JIRA_URL else None
    
    try:
        # Start deployment process
        updates.append(
            Update(
                timestamp=datetime.now().isoformat(),
                message="Starting deployment process",
                type="system"
            )
        )
        
        # Calculate test statistics
        passed_tests = sum(1 for test in request.test_results if test.status == "pass")
        total_tests = len(request.test_results)
        
        # Create branch and commit changes if GitHub token is available
        if GITHUB_TOKEN:
            # Create branch name using convention bugfix/{ticket-id}
            branch_name = request.branch_name or f"bugfix/{request.ticket_id}"
            
            updates.append(
                Update(
                    timestamp=datetime.now().isoformat(),
                    message=f"Creating branch {branch_name}",
                    type="github"
                )
            )
            
            # Create branch
            created_branch = create_branch(request.repository, request.ticket_id)
            if not created_branch:
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message=f"Failed to create branch {branch_name}",
                        type="github"
                    )
                )
                success = False
            else:
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message=f"Successfully created branch {branch_name}",
                        type="github"
                    )
                )
                
                # Prepare file changes from diffs
                file_changes = []
                for diff in request.diffs:
                    # In a real implementation, this would apply the diff to the file
                    # For now, we'll simulate by creating a mock content
                    file_changes.append({
                        'filename': diff.filename,
                        'content': f"// Updated content for {diff.filename}\n// Diff: {diff.diff}"
                    })
                
                # Commit changes
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message=f"Committing changes: {request.commit_message}",
                        type="github"
                    )
                )
                
                commit_success = commit_changes(
                    request.repository,
                    branch_name,
                    file_changes,
                    request.commit_message
                )
                
                if not commit_success:
                    updates.append(
                        Update(
                            timestamp=datetime.now().isoformat(),
                            message="Failed to commit changes",
                            type="github"
                        )
                    )
                    success = False
                else:
                    updates.append(
                        Update(
                            timestamp=datetime.now().isoformat(),
                            message="Successfully committed changes",
                            type="github"
                        )
                    )
                    
                    # Create PR
                    updates.append(
                        Update(
                            timestamp=datetime.now().isoformat(),
                            message=f"Creating pull request for {request.ticket_id}",
                            type="github"
                        )
                    )
                    
                    # Prepare PR description
                    description = f"""
                    Bug fix for {request.ticket_id}
                    
                    Changes:
                    - {request.commit_message}
                    - Files modified: {len(request.diffs)}
                    - Lines added: {sum(diff.lines_added for diff in request.diffs)}
                    - Lines removed: {sum(diff.lines_removed for diff in request.diffs)}
                    
                    Test results:
                    - Passed: {passed_tests}/{total_tests}
                    """
                    
                    pr_url = create_pull_request(
                        request.repository,
                        branch_name,
                        request.ticket_id,
                        request.commit_message,
                        description
                    )
                    
                    if not pr_url:
                        updates.append(
                            Update(
                                timestamp=datetime.now().isoformat(),
                                message="Failed to create pull request",
                                type="github"
                            )
                        )
                        success = False
                    else:
                        updates.append(
                            Update(
                                timestamp=datetime.now().isoformat(),
                                message=f"Pull request created: {pr_url}",
                                type="github"
                            )
                        )
        
        # Update JIRA ticket
        if all([JIRA_TOKEN, JIRA_USER, JIRA_URL]):
            updates.append(
                Update(
                    timestamp=datetime.now().isoformat(),
                    message=f"Updating JIRA ticket {request.ticket_id}",
                    type="jira"
                )
            )
            
            # Determine QA result message
            qa_result = "successful" if passed_tests == total_tests else "failed"
            qa_summary = f"QA tests: {passed_tests}/{total_tests} passed"
            
            # Build detailed comment
            comment = f"""
            BugFix AI: Fix {qa_result}.
            
            {qa_summary}
            
            Summary of changes:
            - {request.commit_message}
            - Files modified: {len(request.diffs)}
            - Total lines added: {sum(diff.lines_added for diff in request.diffs)}
            - Total lines removed: {sum(diff.lines_removed for diff in request.diffs)}
            """
            
            if pr_url:
                comment += f"\nPull Request: {pr_url}"
            
            # Update JIRA with status and comment
            status = "Done" if passed_tests == total_tests else "In Progress"
            jira_update_successful = await update_jira_ticket(
                request.ticket_id, 
                status, 
                comment,
                pr_url
            )
            
            if jira_update_successful:
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message=f"JIRA ticket {request.ticket_id} updated successfully",
                        type="jira"
                    )
                )
            else:
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message=f"Failed to update JIRA ticket {request.ticket_id}",
                        type="jira"
                    )
                )
                success = False
        
        # Final deployment status
        updates.append(
            Update(
                timestamp=datetime.now().isoformat(),
                message="Deployment completed successfully" if success else "Deployment completed with issues",
                type="system"
            )
        )
        
        return DeployResponse(
            ticket_id=request.ticket_id,
            pr_url=pr_url,
            jira_url=jira_url,
            updates=updates,
            success=success
        )
    
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
