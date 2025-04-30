
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
        # Split content into lines
        original_lines = original_content.splitlines()
        result_lines = original_lines.copy()
        
        # Track line offsets as we add/remove lines
        line_offset = 0
        
        # Parse diff lines
        current_line = 0
        lines_to_remove = []
        lines_to_add = []
        
        for line in diff_content.splitlines():
            # Skip diff header lines
            if line.startswith('+++') or line.startswith('---') or line.startswith('@@'):
                continue
                
            # Handle removed lines
            if line.startswith('-'):
                content = line[1:].strip()
                # Find this line in the original content
                found = False
                for i, orig_line in enumerate(original_lines):
                    if orig_line.strip() == content:
                        lines_to_remove.append(i)
                        found = True
                        break
                if not found:
                    logger.warning(f"Could not find line to remove: {content}")
                    
            # Handle added lines
            elif line.startswith('+'):
                content = line[1:]
                lines_to_add.append((current_line, content))
                current_line += 1
            else:
                current_line += 1
        
        # Apply removals (from highest line number to lowest to maintain indices)
        for line_num in sorted(lines_to_remove, reverse=True):
            if 0 <= line_num < len(result_lines):
                result_lines.pop(line_num)
        
        # Apply additions (from lowest line number to highest)
        for line_num, content in sorted(lines_to_add):
            if 0 <= line_num <= len(result_lines):
                result_lines.insert(line_num, content)
        
        return '\n'.join(result_lines)
    
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
            # Extract PR number from URL if needed
            if isinstance(pr_number, str) and not pr_number.isdigit():
                # If pr_number is a URL, extract the number
                url_match = re.search(r'/pull/(\d+)', pr_number)
                if url_match:
                    pr_number = url_match.group(1)
            
            # Convert to int if it's a string with digits
            if isinstance(pr_number, str) and pr_number.isdigit():
                pr_number = int(pr_number)
                
            # Use the GitHubClient instance to add the comment
            return self.client.add_pr_comment(pr_number, comment)
            
        except Exception as e:
            logger.error(f"Error adding comment to PR {pr_number}: {str(e)}")
            return False
