
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import importlib.util
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple
import httpx
import asyncio
import re

# Add the project root to the Python path
sys.path.append('/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("communicator-agent")

# Check if we're in test mode
TEST_MODE = os.environ.get("TEST_MODE", "False").lower() == "true"
DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.debug("Running in DEBUG mode - verbose logging enabled")

if TEST_MODE:
    logger.warning("Running in TEST_MODE - using mock GitHub interactions")

# Import GitHub service from backend
github_service = None
try:
    # First try to import directly from the github_service package
    from backend.github_service.github_service import GitHubService
    github_service = GitHubService()
    logger.info("Successfully imported GitHubService from backend package")
    
    # Verify configuration
    from backend.github_service.config import verify_config, get_repo_info, is_test_mode
    
    if verify_config():
        repo_info = get_repo_info()
        logger.info(f"GitHub configuration verified: {repo_info['owner']}/{repo_info['name']}")
    else:
        logger.error("GitHub configuration verification failed")
        # Don't create a mock if verification fails - let it error out
except ImportError as e:
    logger.warning(f"Error importing GitHub service directly: {str(e)}")
    
    try:
        # Fallback to using the github_utils
        try:
            import github_utils
            create_branch = github_utils.create_branch
            commit_changes = github_utils.commit_changes
            create_pull_request = github_utils.create_pull_request
            logger.info("Successfully imported github_utils directly")
        except ImportError as e:
            logger.warning(f"Error importing github_utils directly: {str(e)}")
            # Try to find github_utils.py in the container
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
                if TEST_MODE:
                    logger.warning("Could not find GitHub utilities - using mock implementations in TEST_MODE")
                    # Create mock implementations for test mode
                    def create_branch(repo, branch_name, base_branch):
                        logger.info(f"[MOCK] Would create branch {branch_name} in {repo} from {base_branch}")
                        return branch_name
                        
                    def commit_changes(repo, branch, files, message):
                        logger.info(f"[MOCK] Would commit {len(files)} files to {branch} in {repo}")
                        return True
                        
                    def create_pull_request(repo, branch, ticket_id, title, body):
                        logger.info(f"[MOCK] Would create PR for {branch} in {repo} for ticket {ticket_id}")
                        # In test mode, return a placeholder PR URL
                        pr_number = int(datetime.now().timestamp()) % 1000  # Use timestamp as PR number
                        if "GITHUB_REPO_OWNER" in os.environ and "GITHUB_REPO_NAME" in os.environ:
                            pr_url = f"https://github.com/{os.environ['GITHUB_REPO_OWNER']}/{os.environ['GITHUB_REPO_NAME']}/pull/{pr_number}"
                        else:
                            pr_url = f"https://github.com/org/repo/pull/{pr_number}"
                        logger.info(f"[MOCK] PR URL: {pr_url}")
                        return pr_url, pr_number
                else:
                    logger.error("Could not find GitHub utilities - PR creation will be unavailable")
    except Exception as inner_e:
        logger.error(f"Error setting up GitHub utils fallback: {str(inner_e)}")

app = FastAPI(title="BugFix AI Communicator Agent")

class FileDiff(BaseModel):
    filename: str
    diff: str
    lines_added: int = 0
    lines_removed: int = 0
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
    repository: Optional[str] = None  # Will use env vars if not provided

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
    
    # Get repository information
    repository = request.repository
    if not repository:
        # Try to get from environment
        repo_owner = os.environ.get("GITHUB_REPO_OWNER")
        repo_name = os.environ.get("GITHUB_REPO_NAME")
        
        if repo_owner and repo_name:
            repository = f"{repo_owner}/{repo_name}"
            logger.info(f"Using repository from environment: {repository}")
        else:
            if TEST_MODE:
                repository = "user/repo"  # Default for test mode
                logger.warning(f"Using default repository for TEST_MODE: {repository}")
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="Repository not provided and GITHUB_REPO_OWNER/GITHUB_REPO_NAME not set in environment"
                )
    
    try:
        # Validate the diffs before proceeding
        all_diffs_valid = await validate_diffs(request.diffs)
        if not all_diffs_valid:
            raise HTTPException(status_code=400, detail="Some diffs are invalid or empty")
        
        # Check if we're using the GitHub service or github_utils
        if github_service:
            # Create a branch for the fix
            branch_name = f"fix/{request.ticket_id.lower()}"
            
            try:
                branch_created, branch_name = github_service.create_fix_branch(
                    request.ticket_id,
                    "main"  # Use main branch as base
                )
                
                if not branch_created:
                    logger.warning("Branch creation returned False - checking if it already exists")
                    # Check if branch already exists
                    existing_branch = github_service.get_branch(branch_name)
                    if not existing_branch:
                        raise HTTPException(status_code=500, detail="Failed to create branch and branch does not exist")
                
                logger.info(f"Branch created or already exists: {branch_name}")
            except Exception as e:
                logger.error(f"Error creating branch: {str(e)}")
                if TEST_MODE:
                    logger.warning("TEST_MODE: Continuing despite branch creation error")
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to create branch: {str(e)}")
            
            # Check if PR already exists
            existing_pr = None
            try:
                existing_pr = github_service.check_for_existing_pr(branch_name, "main")
                if existing_pr:
                    logger.info(f"Found existing PR for branch {branch_name}: {existing_pr['url']}")
            except Exception as e:
                logger.warning(f"Error checking for existing PR: {str(e)}")
            
            pr_number = None
            pr_url = None
            
            if existing_pr:
                pr_url = existing_pr['url']
                # Get PR number from the existing PR
                pr_number = existing_pr.get('number')
                logger.info(f"Using existing PR #{pr_number}")
            else:
                # Format the diffs for the commit
                file_changes = []
                for diff in request.diffs:
                    file_changes.append({
                        "filename": diff.filename,
                        "content": diff.diff
                    })
                
                logger.info(f"Committing {len(file_changes)} file changes to branch {branch_name}")
                
                # Log the actual diff content for debugging in debug mode
                if DEBUG_MODE:
                    for diff in request.diffs:
                        logger.debug(f"Diff for {diff.filename}: {diff.diff[:100]}...")
                
                # Commit the changes
                try:
                    commit_success, commit_details = github_service.commit_bug_fix(
                        branch_name,
                        file_changes,
                        request.ticket_id,
                        request.commit_message
                    )
                    
                    if not commit_success:
                        logger.error(f"Failed to commit changes: {commit_details}")
                        if TEST_MODE:
                            logger.warning("TEST_MODE: Continuing despite commit failure")
                        else:
                            raise HTTPException(status_code=500, detail="Failed to commit changes")
                except Exception as e:
                    logger.error(f"Error committing changes: {str(e)}")
                    if TEST_MODE:
                        logger.warning("TEST_MODE: Continuing despite commit error")
                    else:
                        raise HTTPException(status_code=500, detail=f"Failed to commit changes: {str(e)}")
                
                # Create pull request
                pr_result = None
                try:
                    pr_description = f"Automated bug fix for {request.ticket_id}\n\nThis PR contains the following changes:\n" + \
                                     "\n".join([f"- {diff.filename}: {diff.explanation or 'No explanation provided'}" for diff in request.diffs]) + \
                                     "\n\n### Test Results\n" + \
                                     "\n".join([f"- {test.name}: {test.status}" for test in request.test_results])
                    
                    pr_result = github_service.create_fix_pr(
                        branch_name,
                        request.ticket_id,
                        f"Fix for {request.ticket_id}",
                        pr_description
                    )
                    
                    if not pr_result:
                        logger.error("Failed to create PR - result is None")
                        if TEST_MODE:
                            # Generate a placeholder PR URL for test mode
                            pr_number = int(datetime.now().timestamp()) % 1000
                            pr_url = f"https://github.com/{repository}/pull/{pr_number}"
                            logger.warning(f"TEST_MODE: Using placeholder PR URL: {pr_url}")
                        else:
                            raise HTTPException(status_code=500, detail="Failed to create or find PR")
                    else:
                        # Handle case where url might be a tuple
                        if isinstance(pr_result, tuple) and len(pr_result) > 0:
                            pr_url = pr_result[0]  # Get the URL string
                            pr_number = pr_result[1] if len(pr_result) > 1 else None
                        elif isinstance(pr_result, dict):
                            pr_url = pr_result.get('url')
                            pr_number = pr_result.get('number')
                        else:
                            pr_url = str(pr_result)
                            # Try to extract PR number from URL
                            match = re.search(r"/pull/(\d+)", pr_url)
                            if match:
                                pr_number = int(match.group(1))
                        
                        logger.info(f"PR created at: {pr_url} with number {pr_number}")
                except Exception as e:
                    logger.error(f"Error creating PR: {str(e)}")
                    if TEST_MODE:
                        # Generate a placeholder PR URL for test mode
                        pr_number = int(datetime.now().timestamp()) % 1000
                        pr_url = f"https://github.com/{repository}/pull/{pr_number}"
                        logger.warning(f"TEST_MODE: Using placeholder PR URL after error: {pr_url}")
                    else:
                        raise HTTPException(status_code=500, detail=f"Failed to create PR: {str(e)}")
        else:
            # Fallback to github_utils
            try:
                branch_name = create_branch(
                    repository,
                    request.ticket_id,
                    "main"  # Use main branch as base
                )
                
                if not branch_name:
                    logger.error("Branch creation returned empty branch name")
                    if TEST_MODE:
                        branch_name = f"fix/{request.ticket_id.lower()}"
                        logger.warning(f"TEST_MODE: Using default branch name: {branch_name}")
                    else:
                        raise HTTPException(status_code=500, detail="Failed to create branch")
                
                # Format the diffs for the commit
                file_changes = []
                for diff in request.diffs:
                    file_changes.append({
                        "filename": diff.filename,
                        "content": diff.diff
                    })
                
                # Log the diff details for debugging
                if DEBUG_MODE:
                    for diff in request.diffs:
                        logger.debug(f"Diff for {diff.filename} (github_utils): {diff.diff[:100]}...")
                
                # Commit the changes
                commit_success = commit_changes(
                    repository,
                    branch_name,
                    file_changes,
                    request.commit_message
                )
                
                if not commit_success:
                    logger.error("Failed to commit changes")
                    if TEST_MODE:
                        logger.warning("TEST_MODE: Continuing despite commit failure")
                    else:
                        raise HTTPException(status_code=500, detail="Failed to commit changes")
                
                # Create pull request
                pr_description = f"Automated bug fix for {request.ticket_id}\n\nThis PR contains the following changes:\n" + \
                                "\n".join([f"- {diff.filename}: {diff.explanation or 'No explanation provided'}" for diff in request.diffs])
                
                pr_result = create_pull_request(
                    repository,
                    branch_name,
                    request.ticket_id,
                    f"Fix for {request.ticket_id}",
                    pr_description
                )
                
                # Handle case where pr_url might be a tuple
                if isinstance(pr_result, tuple) and len(pr_result) > 0:
                    pr_url = pr_result[0]  # Get the URL string
                    pr_number = pr_result[1] if len(pr_result) > 1 else None
                else:
                    pr_url = str(pr_result)
                    # Try to extract PR number
                    match = re.search(r"/pull/(\d+)", pr_url)
                    if match:
                        pr_number = int(match.group(1))
                    else:
                        pr_number = None
                
                logger.info(f"PR created at: {pr_url}")
            except Exception as e:
                logger.error(f"Error in github_utils flow: {str(e)}")
                if TEST_MODE:
                    # Generate a placeholder PR URL for test mode
                    pr_number = int(datetime.now().timestamp()) % 1000
                    pr_url = f"https://github.com/{repository}/pull/{pr_number}"
                    logger.warning(f"TEST_MODE: Using placeholder PR URL after exception: {pr_url}")
                else:
                    raise HTTPException(status_code=500, detail=f"Error in PR creation: {str(e)}")
        
        # Add a comment to the PR if it exists and we have a PR number
        if pr_url and pr_number:
            comment = f"This PR was created automatically by BugFix AI to fix issue {request.ticket_id}\n\n"
            comment += "Test results:\n"
            for test in request.test_results:
                status_emoji = "✅" if test.status == "passed" else "❌"
                comment += f"- {status_emoji} {test.name}: {test.status}\n"
            
            try:
                if github_service:
                    # Use the PR number directly, not the ticket ID
                    comment_success = await post_pr_comment_with_service(pr_number, comment)
                else:
                    # Use github_utils or simulated comment in test mode
                    logger.info(f"Would add comment to PR #{pr_number}: {comment[:100]}...")
                    comment_success = True
                
                if comment_success:
                    logger.info(f"Successfully added comment to PR #{pr_number}")
                else:
                    logger.warning(f"Failed to add comment to PR #{pr_number}")
            except Exception as e:
                logger.error(f"Error adding comment to PR {pr_url}: {str(e)}")
        
        # Update JIRA ticket status
        jira_success = await update_jira_ticket(request.ticket_id, pr_url)
        
        # Send notifications
        await send_notifications(request.ticket_id, pr_url, repository)
        
        logger.info(f"Deployment successful for ticket {request.ticket_id}, PR created at {pr_url}")
        
        return DeployResponse(
            ticket_id=request.ticket_id,
            jira_status="Ready for Review",
            pr_url=pr_url
        )
    
    except Exception as e:
        logger.error(f"Error deploying fix for ticket {request.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deploying fix: {str(e)}")

async def validate_diffs(diffs: List[FileDiff]) -> bool:
    """Validate diffs to ensure they're not empty or invalid"""
    if not diffs:
        logger.error("No diffs provided")
        return False
        
    for diff in diffs:
        if not diff.filename:
            logger.error("Diff missing filename")
            return False
            
        if not diff.diff or diff.diff.strip() == "":
            logger.error(f"Empty diff for file {diff.filename}")
            return False
            
        # Validate diff format - should contain unified diff markers
        if not ("@@" in diff.diff and (diff.diff.startswith("--- ") or diff.diff.startswith("diff --git"))):
            logger.warning(f"Diff for {diff.filename} doesn't appear to be in unified format")
            
            # Log the actual content for debugging
            if DEBUG_MODE:
                logger.debug(f"Invalid diff content: {diff.diff[:100]}...")
            
            # Don't reject entirely - might be a raw replacement diff
            # But do log the issue
    
    logger.info(f"All {len(diffs)} diffs validated successfully")
    return True

async def post_pr_comment_with_service(pr_number: int, comment: str) -> bool:
    """Post a comment to a GitHub PR using the GitHub service"""
    if not github_service:
        logger.warning("GitHub service not available for PR comment")
        return False
    
    try:
        logger.info(f"Attempting to post comment to PR #{pr_number}")
        
        # Try up to 3 times with a delay between attempts
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                # Use the GitHub service to post the comment using the PR number
                result = github_service.add_pr_comment(pr_number, comment)
                if result:
                    logger.info(f"Successfully added comment to PR on attempt {attempt}")
                    return True
                else:
                    logger.warning(f"Failed to add comment to PR on attempt {attempt}")
                    if attempt < max_retries:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error posting comment to PR on attempt {attempt}: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
        
        logger.error(f"Max retries reached for GitHub comment on PR #{pr_number}")
        return False
    except Exception as e:
        logger.error(f"Error preparing PR comment: {str(e)}")
        return False

async def update_jira_ticket(ticket_id: str, pr_url: Optional[str] = None) -> bool:
    """Update the JIRA ticket with PR information"""
    try:
        # Get JIRA credentials from environment
        jira_token = os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_TOKEN")
        jira_user = os.environ.get("JIRA_USERNAME") or os.environ.get("JIRA_USER")
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
                            "text": f"Bug fix implemented by BugFix AI. Pull request: {pr_url}",
                            "type": "text"
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

@app.post("/cleanup/branch/{branch_name}")
async def cleanup_branch(branch_name: str):
    """API endpoint to clean up a branch after PR is merged or closed"""
    if not github_service:
        raise HTTPException(status_code=500, detail="GitHub service not available")
        
    try:
        logger.info(f"Cleaning up branch {branch_name}")
        success = github_service.delete_branch(branch_name)
        
        if success:
            return {"message": f"Successfully deleted branch {branch_name}"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to delete branch {branch_name}")
    except Exception as e:
        logger.error(f"Error cleaning up branch {branch_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up branch: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8004, reload=True)
