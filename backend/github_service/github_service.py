
import logging
from typing import Dict, Any, Optional, List, Tuple
import re
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
            self.token = self.client.token
            self.repo_owner = self.client.repo.owner.login if self.client.repo else None
            self.repo_name = self.client.repo.name if self.client.repo else None
            self.repo_api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None
            self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"} if self.token else None
        except (ValueError, GithubException) as e:
            logger.error(f"Failed to initialize GitHub service: {str(e)}")
            self.client = None
            self.token = None
            self.repo_owner = None
            self.repo_name = None
            self.repo_api_url = None
            self.headers = None
    
    def create_fix_branch(self, ticket_id: str, base_branch: str = None) -> Optional[str]:
        """Create a new branch for fixing a bug."""
        if not self.client:
            logger.error("GitHub client not initialized")
            return None
            
        branch_name = f"fix/{ticket_id}"
        
        # Check if branch already exists
        try:
            if self.client.check_branch_exists(branch_name):
                logger.info(f"Branch {branch_name} already exists, will reuse it")
                # Instead of skipping, we'll reuse the existing branch
                # Optionally, we could reset the branch to base_branch here if needed
                return branch_name
        except Exception as e:
            logger.error(f"Error checking if branch {branch_name} exists: {str(e)}")
        
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
            # Extract diff content from GPT output using regex
            diff_pattern = r'```diff\s+([\s\S]+?)\s+```'
            diff_match = re.search(diff_pattern, gpt_output)
            
            if not diff_match:
                logger.warning(f"No diff found in GPT output for ticket {ticket_id}")
                
                # Try alternative pattern for code blocks
                code_pattern = r'```(?:python|javascript|typescript)?\s+([\s\S]+?)\s+```'
                code_match = re.search(code_pattern, gpt_output)
                
                if not code_match:
                    logger.error("No code block found in GPT output")
                    return False
                    
                # Use the entire code block as replacement
                new_content = code_match.group(1).strip()
                logger.info(f"Using entire code block as replacement for {file_path}")
                
                file_changes = [{
                    'filename': file_path,
                    'content': new_content
                }]
                
                commit_message = f"Fix {ticket_id}: Replace {file_path} with GPT suggestion"
                return self.commit_bug_fix(branch_name, file_changes, ticket_id, commit_message)
            
            # If we have a diff, apply it properly
            diff_content = diff_match.group(1)
            
            # Get current file content
            current_content = self.client.get_file_content(file_path, branch_name)
            if not current_content:
                logger.error(f"Failed to get current content for {file_path}")
                return False
                
            # Apply the diff to the current content (improved implementation)
            new_content = self._apply_diff(current_content, diff_content)
            
            # Commit the changes
            file_changes = [{
                'filename': file_path,
                'content': new_content
            }]
            
            commit_message = f"Fix {ticket_id}: Apply GPT suggestions to {file_path}"
            return self.commit_bug_fix(branch_name, file_changes, ticket_id, commit_message)
                
        except Exception as e:
            logger.error(f"Error applying GPT changes to {file_path}: {str(e)}")
            return False
            
    def _apply_diff(self, original_content: str, diff_content: str) -> str:
        """
        Apply a diff to original content
        
        Args:
            original_content: Original file content
            diff_content: Diff content in unified diff format
            
        Returns:
            str: New content with diff applied
        """
        # ... keep existing code (diff application logic)
    
    def check_for_existing_pr(self, branch_name: str, base_branch: str = None) -> Optional[Dict[str, Any]]:
        """
        Check if a PR already exists for the specified branch.
        
        Args:
            branch_name: The name of the branch to check
            base_branch: The base branch for the PR
            
        Returns:
            Optional[Dict[str, Any]]: PR information if found, None otherwise
        """
        if not self.client or not self.repo_owner or not self.repo_name or not self.token:
            logger.error("GitHub client not properly initialized")
            return None
        
        try:
            # Format the request for GitHub API
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }
            params = {"state": "open", "head": f"{self.repo_owner}:{branch_name}"}
            
            import requests
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                prs = response.json()
                if prs and len(prs) > 0:
                    # Return information about the existing PR
                    pr = prs[0]  # Take the first matching PR
                    logger.info(f"Found existing PR #{pr['number']} for branch {branch_name}")
                    return {
                        "number": pr["number"],
                        "url": pr["html_url"],
                        "state": pr["state"],
                        "title": pr["title"],
                        "created_at": pr["created_at"]
                    }
            else:
                logger.error(f"Failed to check for existing PR: {response.status_code}, {response.text}")
            
            return None
        except Exception as e:
            logger.error(f"Error checking for existing PR: {str(e)}")
            return None
    
    def create_fix_pr(self, branch_name: str, ticket_id: str, title: str,
                     description: str, base_branch: str = None) -> Optional[str]:
        """Create a pull request for the bug fix."""
        if not self.client:
            logger.error("GitHub client not initialized")
            return None
        
        # First check if a PR already exists
        existing_pr = self.check_for_existing_pr(branch_name, base_branch)
        if existing_pr:
            logger.info(f"PR already exists for branch {branch_name}: {existing_pr['url']}")
            return existing_pr['url']
            
        pr_title = f"Fix {ticket_id}: {title}"
        pr_body = f"""
## Bug Fix: {ticket_id}

### Description
{description}

### Changes Made
- Bug fix implementation
- Automated PR created by BugFix AI
        """
        
        # Create PR using the configured repository information
        return self.client.create_pull_request(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=base_branch
        )
    
    def add_pr_comment(self, pr_identifier, comment: str) -> bool:
        """
        Add a comment to a pull request
        
        Args:
            pr_identifier: PR number or URL 
            comment: The comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client or not self.repo_owner or not self.repo_name or not self.token:
            logger.error("GitHub client not properly initialized")
            return False
        
        try:
            # Extract PR number from URL if needed
            pr_number = pr_identifier
            if isinstance(pr_identifier, str):
                # If it's a URL, extract the number
                url_match = re.search(r'/pull/(\d+)', pr_identifier)
                if url_match:
                    pr_number = url_match.group(1)
                    
                # Handle cases where ticket_id is passed as PR identifier erroneously
                if not url_match and not str(pr_identifier).isdigit():
                    logger.warning(f"Invalid PR identifier: {pr_identifier}, appears to be a ticket ID not a PR number")
                    
                    # Try to find the PR by looking for a branch named fix/{pr_identifier}
                    branch_name = f"fix/{pr_identifier}"
                    existing_pr = self.check_for_existing_pr(branch_name)
                    
                    if existing_pr and "number" in existing_pr:
                        logger.info(f"Found PR #{existing_pr['number']} for ticket {pr_identifier}")
                        pr_number = existing_pr["number"]
                    else:
                        logger.error(f"Could not find PR for ticket {pr_identifier}")
                        return False
            
            # Ensure pr_number is an integer
            try:
                pr_number = int(pr_number)
            except (ValueError, TypeError):
                logger.error(f"Could not convert PR identifier '{pr_number}' to integer")
                return False
                
            # Use the GitHub API to add the comment
            import requests
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues/{pr_number}/comments"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {"body": comment}
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code in [201, 200]:
                logger.info(f"Successfully added comment to PR #{pr_number}")
                return True
            else:
                logger.error(f"Failed to add comment to PR #{pr_number}: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding comment to PR {pr_identifier}: {str(e)}")
            return False
    
    def find_pr_for_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a pull request associated with a ticket ID
        
        Args:
            ticket_id: The ticket ID to search for
            
        Returns:
            Optional[Dict[str, Any]]: PR information if found, None otherwise
        """
        if not self.client:
            logger.error("GitHub client not initialized")
            return None
            
        # First try looking for a branch with the ticket ID
        branch_name = f"fix/{ticket_id}"
        
        try:
            # Check if the branch exists
            exists = self.client.check_branch_exists(branch_name)
            if not exists:
                logger.info(f"No branch found for ticket {ticket_id}")
                return None
                
            # Look for PRs from this branch
            pr_data = self.client.find_pr_for_branch(branch_name)
            if pr_data:
                logger.info(f"Found PR #{pr_data['number']} for ticket {ticket_id}")
                return pr_data
                
            # Alternatively, search for PRs with the ticket ID in the title
            # This is left as a future enhancement
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding PR for ticket {ticket_id}: {str(e)}")
            return None
            
    def delete_branch(self, branch_name: str) -> bool:
        """
        Delete a branch from the repository
        
        Args:
            branch_name: The name of the branch to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client or not self.repo_api_url or not self.headers:
            logger.error("GitHub client not properly initialized")
            return False
            
        try:
            # Check if branch exists first to avoid unnecessary API calls
            if not self.client.check_branch_exists(branch_name):
                logger.info(f"Branch {branch_name} does not exist, no need to delete")
                return True
                
            # Format the request for GitHub API
            import requests
            url = f"{self.repo_api_url}/git/refs/heads/{branch_name}"
            
            response = requests.delete(url, headers=self.headers)
            
            if response.status_code in [204, 200]:
                logger.info(f"Successfully deleted branch {branch_name}")
                return True
            else:
                logger.error(f"Failed to delete branch {branch_name}: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error deleting branch {branch_name}: {str(e)}")
            return False
