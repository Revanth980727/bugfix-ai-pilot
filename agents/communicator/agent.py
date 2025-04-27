
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
import httpx
from jira import JIRA
import asyncio
from slack_sdk.web.async_client import AsyncWebClient
import aiosmtplib
from email.mime.text import MIMEText
import sys
import importlib.util
from pathlib import Path
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("communicator-agent")

# Load github_utils directly from the file
github_utils_path = Path("/app/backend/github_utils.py")
if not github_utils_path.exists():
    # Look in parent directory for local development
    github_utils_path = Path(__file__).parent.parent.parent / "backend" / "github_utils.py"

if github_utils_path.exists():
    spec = importlib.util.spec_from_file_location("github_utils", str(github_utils_path))
    github_utils = importlib.util.module_from_spec(spec)
    
    # Create a simple env module with GITHUB_TOKEN for github_utils.py
    env_module = type('EnvModule', (), {'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN')})
    sys.modules['env'] = env_module
    
    spec.loader.exec_module(github_utils)
    create_branch = github_utils.create_branch
    commit_changes = github_utils.commit_changes
    create_pull_request = github_utils.create_pull_request
else:
    logger.error(f"Could not find github_utils.py at {github_utils_path}")
    # Provide stub functions to prevent crashes
    def create_branch(*args, **kwargs):
        logger.error("github_utils not available: create_branch called")
        return None
    def commit_changes(*args, **kwargs):
        logger.error("github_utils not available: commit_changes called")
        return False
    def create_pull_request(*args, **kwargs):
        logger.error("github_utils not available: create_pull_request called")
        return None

# Get environment variables
JIRA_TOKEN = os.getenv('JIRA_TOKEN')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_URL = os.getenv('JIRA_URL')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL')

app = FastAPI(title="BugFix AI Communicator Agent")

# ... keep existing code (model class definitions for FileDiff, TestResult, QAResponse, etc)

async def send_slack_notification(message: str) -> bool:
    """Send a notification to Slack"""
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        return False
        
    try:
        client = AsyncWebClient(token=SLACK_TOKEN)
        await client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message
        )
        return True
    except Exception as e:
        logger.error(f"Error sending Slack notification: {str(e)}")
        return False

async def send_email_notification(subject: str, body: str) -> bool:
    """Send an email notification"""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, NOTIFICATION_EMAIL]):
        return False
        
    try:
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = SMTP_USER
        message["To"] = NOTIFICATION_EMAIL
        
        smtp = aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT, use_tls=True)
        await smtp.connect()
        await smtp.login(SMTP_USER, SMTP_PASSWORD)
        await smtp.send_message(message)
        await smtp.quit()
        return True
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        return False

async def update_jira_with_custom_fields(
    ticket_id: str, 
    status: str,
    comment: str,
    needs_review: bool,
    pr_url: Optional[str] = None
) -> bool:
    """Update JIRA ticket with status, comment, and custom fields"""
    try:
        auth = (JIRA_USER, JIRA_TOKEN)
        jira_instance = JIRA(server=JIRA_URL, basic_auth=auth)
        
        # Add comment
        jira_instance.add_comment(ticket_id, comment)
        
        # Update status
        if status:
            transitions = jira_instance.transitions(ticket_id)
            transition_id = None
            
            for t in transitions:
                if status.lower() in t['name'].lower():
                    transition_id = t['id']
                    break
                    
            if transition_id:
                jira_instance.transition_issue(ticket_id, transition_id)
        
        # Update custom fields
        fields = {}
        
        # Add custom field for human review if configured
        review_field = os.getenv('JIRA_NEEDS_REVIEW_FIELD')
        if review_field:
            fields[review_field] = needs_review
            
        # Add PR link if provided
        if pr_url:
            jira_instance.add_simple_link(ticket_id, {
                'url': pr_url,
                'title': 'GitHub Pull Request'
            })
            
        # Update fields if any were set
        if fields:
            jira_instance.issue(ticket_id).update(fields=fields)
            
        return True
    except Exception as e:
        logger.error(f"Error updating JIRA ticket {ticket_id}: {str(e)}")
        return False

# ... keep existing code (API endpoints and implementation)

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
        # ... keep existing code (deployment process implementation)
        
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
        all_tests_passed = passed_tests == total_tests
        
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
        
        if all_tests_passed:
            # Update JIRA with success status
            jira_comment = f"""
            BugFix AI: Fix successful.
            
            Test Results: {passed_tests}/{total_tests} tests passed
            Changes made: {request.commit_message}
            """
            
            if pr_url:
                jira_comment += f"\nPull Request: {pr_url}"
                
            await update_jira_with_custom_fields(
                request.ticket_id,
                "Done",
                jira_comment,
                needs_review=False,
                pr_url=pr_url
            )
            
            updates.append(
                Update(
                    timestamp=datetime.now().isoformat(),
                    message="JIRA ticket updated with success status",
                    type="jira"
                )
            )
        else:
            # Handle test failures
            success = False
            failed_tests = [test for test in request.test_results if test.status == "fail"]
            
            # Update JIRA with failure status
            jira_comment = f"""
            BugFix AI: Fix requires human review.
            
            Test Results: {passed_tests}/{total_tests} tests passed
            Failed Tests:
            {chr(10).join(f'- {test.name}: {test.error_message}' for test in failed_tests)}
            """
            
            await update_jira_with_custom_fields(
                request.ticket_id,
                "Needs Review",
                jira_comment,
                needs_review=True
            )
            
            updates.append(
                Update(
                    timestamp=datetime.now().isoformat(),
                    message="JIRA ticket updated with failure status",
                    type="jira"
                )
            )
            
            # Send notifications for human review needed
            notification_message = f"BugFix AI: Ticket {request.ticket_id} requires human review. {passed_tests}/{total_tests} tests passed."
            
            # Send Slack notification if configured
            if SLACK_TOKEN:
                await send_slack_notification(notification_message)
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message="Sent Slack notification for human review",
                        type="system"
                    )
                )
            
            # Send email notification if configured
            if all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, NOTIFICATION_EMAIL]):
                await send_email_notification(
                    f"Human Review Required - Ticket {request.ticket_id}",
                    notification_message
                )
                updates.append(
                    Update(
                        timestamp=datetime.now().isoformat(),
                        message="Sent email notification for human review",
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
