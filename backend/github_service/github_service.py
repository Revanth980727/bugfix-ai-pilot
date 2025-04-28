
import logging
from typing import Dict, Any, Optional, List
from .github_client import GitHubClient
from .config import verify_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service")

class GitHubService:
    def __init__(self):
        verify_config()
        self.client = GitHubClient()
    
    def create_fix_branch(self, ticket_id: str, base_branch: str = None) -> Optional[str]:
        """Create a new branch for fixing a bug."""
        branch_name = f"fix/{ticket_id}"
        return self.client.create_branch(branch_name, base_branch)
    
    def commit_bug_fix(self, branch_name: str, file_changes: List[Dict[str, Any]], 
                      ticket_id: str, description: str) -> bool:
        """Commit bug fix changes to a branch."""
        commit_message = f"Fix {ticket_id}: {description}"
        return self.client.commit_changes(branch_name, file_changes, commit_message)
    
    def create_fix_pr(self, branch_name: str, ticket_id: str, title: str,
                     description: str, base_branch: str = None) -> Optional[str]:
        """Create a pull request for the bug fix."""
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
            branch_name=branch_name,
            title=pr_title,
            body=pr_body,
            base_branch=base_branch
        )
