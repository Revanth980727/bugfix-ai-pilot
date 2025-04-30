
import logging
from typing import Dict, Any, Optional, List, Tuple
from github import GithubException
from .github_client import GitHubClient
from .config import verify_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service")

class GitHubService:
    def __init__(self):
        try:
            verify_config()
            self.client = GitHubClient()
        except (ValueError, GithubException) as e:
            logger.error(f"Failed to initialize GitHub service: {str(e)}")
            self.client = None
    
    def create_fix_branch(self, ticket_id: str, base_branch: str = None) -> Optional[str]:
        """Create a new branch for fixing a bug."""
        if not self.client:
            logger.error("GitHub client not initialized")
            return None
            
        branch_name = f"fix/{ticket_id}"
        return self.client.create_branch(branch_name, base_branch)
    
    def commit_bug_fix(self, branch_name: str, file_changes: List[Dict[str, Any]], 
                      ticket_id: str, description: str) -> bool:
        """Commit bug fix changes to a branch."""
        if not self.client:
            logger.error("GitHub client not initialized")
            return False
            
        commit_message = f"Fix {ticket_id}: {description}"
        return self.client.commit_changes(branch_name, file_changes, commit_message)
    
    def create_fix_pr(self, branch_name: str, ticket_id: str, title: str,
                     description: str, base_branch: str = None) -> Optional[str]:
        """Create a pull request for the bug fix."""
        if not self.client:
            logger.error("GitHub client not initialized")
            return None
            
        pr_title = f"Fix {ticket_id}: {title}"
        pr_body = f"""
## Bug Fix: {ticket_id}

### Description
{description}

### Changes Made
- Bug fix implementation
- Automated PR created by BugFix AI
        """
        
        return self.client.create_pull_request(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=base_branch
        )
        
    async def add_pr_comment(self, pr_number: str, comment: str) -> bool:
        """
        Add a comment to a pull request
        
        Args:
            pr_number: The PR number or ID
            comment: The comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            logger.error("GitHub client not initialized")
            return False
            
        try:
            # Convert pr_number to int if it's a string
            if isinstance(pr_number, str) and pr_number.isdigit():
                pr_number = int(pr_number)
            
            logger.info(f"Adding comment to PR {pr_number}")
            
            # Use the client to add the comment
            # Note: This assumes the client has a method to add PR comments
            # If it doesn't, you'll need to implement that in GitHubClient as well
            if hasattr(self.client, 'add_pr_comment'):
                return self.client.add_pr_comment(pr_number, comment)
            else:
                # Fallback to direct API call if client doesn't support it
                repo = f"{self.client.repo_owner}/{self.client.repo_name}"
                url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
                
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": f"token {self.client.token}",
                    "Content-Type": "application/json"
                }
                
                payload = {"body": comment}
                
                # Use the requests library directly
                import requests
                response = requests.post(url, headers=headers, json=payload)
                
                if response.status_code not in (201, 200):
                    logger.error(f"Failed to add comment to PR {pr_number}: {response.status_code}, {response.text}")
                    return False
                
                logger.info(f"Successfully added comment to PR {pr_number}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding comment to PR {pr_number}: {str(e)}")
            return False
