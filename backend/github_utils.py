
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from github import Github, GithubException

# Try importing GITHUB_TOKEN from env.py if it exists, otherwise use environment variable
try:
    from env import GITHUB_TOKEN
except ImportError:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-utils")

def authenticate_github():
    """Authenticate with GitHub using the personal access token"""
    if not GITHUB_TOKEN:
        logger.error("GitHub token not found. Please set GITHUB_TOKEN environment variable.")
        return None
        
    try:
        github_client = Github(GITHUB_TOKEN)
        # Test the connection
        user = github_client.get_user()
        logger.info(f"Authenticated as GitHub user: {user.login}")
        return github_client
    except GithubException as e:
        logger.error(f"GitHub authentication error: {str(e)}")
        return None

def create_branch(repo_name: str, ticket_id: str, base_branch: str = "main") -> Optional[str]:
    """Create a new branch for the bugfix"""
    try:
        github_client = authenticate_github()
        if not github_client:
            return None
            
        # Get the repository
        repo = github_client.get_repo(repo_name)
        
        # Get the base branch to branch off from
        try:
            base_ref = repo.get_branch(base_branch)
        except GithubException as e:
            logger.error(f"Base branch '{base_branch}' not found: {str(e)}")
            return None
            
        # Create branch name using convention bugfix/{ticket-id}
        branch_name = f"bugfix/{ticket_id}"
        
        # Check if branch already exists
        try:
            repo.get_branch(branch_name)
            logger.info(f"Branch {branch_name} already exists, reusing it")
            return branch_name
        except GithubException:
            # Branch doesn't exist, create it
            try:
                repo.create_git_ref(f"refs/heads/{branch_name}", base_ref.commit.sha)
                logger.info(f"Created branch {branch_name} from {base_branch}")
                return branch_name
            except GithubException as e:
                logger.error(f"Failed to create branch {branch_name}: {str(e)}")
                return None
    except Exception as e:
        logger.error(f"Error creating branch: {str(e)}")
        return None

def commit_changes(repo_name: str, branch_name: str, file_changes: List[Dict[str, Any]], 
                commit_message: str) -> bool:
    """Commit file changes to the branch"""
    try:
        github_client = authenticate_github()
        if not github_client:
            return False
            
        # Get the repository and branch reference
        repo = github_client.get_repo(repo_name)
        
        for file_change in file_changes:
            filename = file_change.get('filename')
            content = file_change.get('content')
            
            if not filename or not content:
                logger.warning(f"Skipping invalid file change: {file_change}")
                continue
                
            try:
                # Check if file exists
                try:
                    file_content = repo.get_contents(filename, ref=branch_name)
                    # Update existing file
                    repo.update_file(
                        path=filename,
                        message=f"Update {filename} - {commit_message}",
                        content=content,
                        sha=file_content.sha,
                        branch=branch_name
                    )
                    logger.info(f"Updated file {filename} in {branch_name}")
                except GithubException:
                    # File doesn't exist, create it
                    repo.create_file(
                        path=filename,
                        message=f"Create {filename} - {commit_message}",
                        content=content,
                        branch=branch_name
                    )
                    logger.info(f"Created file {filename} in {branch_name}")
            except GithubException as e:
                logger.error(f"Failed to update/create file {filename}: {str(e)}")
                return False
                
        return True
    except Exception as e:
        logger.error(f"Error committing changes: {str(e)}")
        return False

def create_pull_request(repo_name: str, branch_name: str, ticket_id: str, title: str, 
                      description: str, base_branch: str = "main") -> Optional[str]:
    """Create a pull request from the bugfix branch to the base branch"""
    try:
        github_client = authenticate_github()
        if not github_client:
            return None
            
        # Get the repository
        repo = github_client.get_repo(repo_name)
        
        # Create PR title
        pr_title = f"Fix for {ticket_id}: {title}"
        
        # Create PR body with ticket link and summary
        jira_url = os.getenv('JIRA_URL', '')
        ticket_link = f"{jira_url}/browse/{ticket_id}" if jira_url else ticket_id
        
        pr_body = f"""
## Bug Fix: {ticket_id}

**JIRA Ticket:** [{ticket_id}]({ticket_link})

### Summary of Changes
{description}

### Automated PR
This PR was automatically generated by BugFix AI.
        """
        
        # Create the PR
        try:
            pull = repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=branch_name,
                base=base_branch
            )
            
            # Add labels
            pull.add_to_labels("autofix", "bug")
            
            logger.info(f"Created PR #{pull.number} for {ticket_id}")
            return pull.html_url
        except GithubException as e:
            logger.error(f"Failed to create PR: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Error creating PR: {str(e)}")
        return None
