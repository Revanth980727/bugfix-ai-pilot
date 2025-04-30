
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
            self.token = self.client.client.get_user().login if self.client else None
            self.repo_owner = self.client.repo.owner.login if self.client else None
            self.repo_name = self.client.repo.name if self.client else None
        except (ValueError, GithubException) as e:
            logger.error(f"Failed to initialize GitHub service: {str(e)}")
            self.client = None
            self.token = None
            self.repo_owner = None
            self.repo_name = None
    
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
    
    def apply_file_changes_from_gpt(self, branch_name: str, file_path: str, gpt_output: str, 
                                   ticket_id: str) -> bool:
        """
        Apply changes suggested by GPT-4 to a file and commit them
        
        Args:
            branch_name: Branch to commit changes to
            file_path: Path of file to update
            gpt_output: The output from GPT with suggested changes
            ticket_id: The JIRA ticket ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client:
            logger.error("GitHub client not initialized")
            return False
            
        try:
            # Extract diff content from GPT output
            import re
            diff_pattern = r'```diff\s+([\s\S]+?)\s+```'
            diff_match = re.search(diff_pattern, gpt_output)
            
            if not diff_match:
                logger.warning(f"No diff found in GPT output for ticket {ticket_id}")
                return False
                
            diff_content = diff_match.group(1)
            
            # Parse changes from diff
            file_changes = []
            current_file = None
            
            # Get current file content
            try:
                current_content = self.client.get_file_content(file_path, branch_name)
                
                # Apply diff (simplified - would need proper diff parser for real use)
                # Here we're just looking for lines with + and - at the beginning
                
                new_lines = []
                for line in current_content.split('\n'):
                    # Check if this line should be removed based on the diff
                    if any(l.startswith('- ' + line) for l in diff_content.split('\n')):
                        continue  # Skip this line as it's removed
                    new_lines.append(line)
                
                # Add new lines that start with +
                for line in diff_content.split('\n'):
                    if line.startswith('+ '):
                        new_lines.append(line[2:])  # Add without the '+ ' prefix
                
                new_content = '\n'.join(new_lines)
                
                # Commit the changes
                file_changes.append({
                    'filename': file_path,
                    'content': new_content
                })
                
                commit_message = f"Fix {ticket_id}: Apply GPT suggestions to {file_path}"
                return self.commit_bug_fix(branch_name, file_changes, ticket_id, commit_message)
                
            except Exception as e:
                logger.error(f"Error applying GPT changes to {file_path}: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing GPT output for {ticket_id}: {str(e)}")
            return False
    
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
            
            try:
                # Try to get pull request
                pr = self.client.repo.get_pull(pr_number)
                pr.create_issue_comment(comment)
                logger.info(f"Successfully added comment to PR {pr_number}")
                return True
            except Exception as e:
                logger.warning(f"Failed to add PR comment using PyGithub API: {str(e)}")
                
                # Fallback to direct API call
                repo = f"{self.repo_owner}/{self.repo_name}"
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

