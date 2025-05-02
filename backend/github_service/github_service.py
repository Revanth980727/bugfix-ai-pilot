import os
import re
import logging
import subprocess
import tempfile
import requests
from typing import Dict, Any, List, Optional, Union
from github import Github, GithubException
from .config import GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_DEFAULT_BRANCH

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service")

class GitHubService:
    def __init__(self, github_token=None, repo_owner=None, repo_name=None, default_branch=None):
        """Initialize GitHub service with API token and configuration"""
        self.github_token = github_token or GITHUB_TOKEN
        self.repo_owner = repo_owner or GITHUB_REPO_OWNER
        self.repo_name = repo_name or GITHUB_REPO_NAME
        self.default_branch = default_branch or GITHUB_DEFAULT_BRANCH
        self.default_repo = f"{self.repo_owner}/{self.repo_name}" if self.repo_owner and self.repo_name else None
        
        if not self.github_token:
            logger.warning("GitHub token not provided. Some functionality will be limited.")
            self.client = None
        else:
            self.client = Github(self.github_token)
    
    def create_fix_branch(self, ticket_id: str, base_branch: str = None) -> bool:
        """
        Create a new branch for a bug fix
        
        Args:
            ticket_id: The JIRA ticket ID
            base_branch: The branch to base the new branch on (defaults to default_branch)
            
        Returns:
            bool: True if branch creation was successful, False otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot create branch")
            return False
            
        base_branch = base_branch or self.default_branch
        new_branch_name = f"fix/{ticket_id}"
        
        try:
            repo = self.client.get_repo(self.default_repo)
            
            # Check if the branch already exists
            try:
                ref = repo.get_git_ref(f"refs/heads/{new_branch_name}")
                logger.info(f"Branch {new_branch_name} already exists")
                return True
            except GithubException as e:
                if e.status != 404:
                    logger.error(f"Error checking if branch exists: {str(e)}")
                    return False
            
            # Get the commit of the base branch
            base_branch_object = repo.get_branch(base_branch)
            base_commit_sha = base_branch_object.commit.sha
            
            # Create the new branch
            repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_commit_sha)
            logger.info(f"Branch {new_branch_name} created successfully")
            return True
        except GithubException as e:
            logger.error(f"GitHub error creating branch: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error creating branch: {str(e)}")
            return False
    
    def commit_bug_fix(self, branch_name: str, file_changes: List[Dict[str, str]], ticket_id: str, commit_message: str) -> bool:
        """
        Commit a bug fix to a branch
        
        Args:
            branch_name: The name of the branch to commit to
            file_changes: A list of dictionaries containing the filename and content of the changes
            ticket_id: The JIRA ticket ID
            commit_message: The commit message
            
        Returns:
            bool: True if commit was successful, False otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot commit changes")
            return False
            
        try:
            repo = self.client.get_repo(self.default_repo)
            
            # Get the branch
            branch = repo.get_branch(branch_name)
            base_tree = branch.commit.commit.tree
            
            # Create a new tree
            element_list = []
            for file_change in file_changes:
                filename = file_change["filename"]
                content = file_change["content"]
                
                element = {
                    "path": filename,
                    "mode": "100644",
                    "type": "blob",
                    "content": content
                }
                element_list.append(element)
            
            tree = repo.create_git_tree(element_list, base_tree=base_tree)
            
            # Create the commit
            if not commit_message.startswith(f"Fix {ticket_id}"):
                commit_message = f"Fix {ticket_id}: {commit_message}"
            
            parent_commit = repo.get_commit(sha=branch.commit.sha)
            commit = repo.create_git_commit(
                message=commit_message,
                tree=tree,
                parents=[parent_commit]
            )
            
            # Update the reference
            ref = repo.get_git_ref(f"refs/heads/{branch_name}")
            ref.edit(sha=commit.sha)
            
            logger.info(f"Changes committed to branch {branch_name} successfully")
            return True
        except GithubException as e:
            logger.error(f"GitHub error committing changes: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error committing changes: {str(e)}")
            return False
    
    def create_fix_pr(self, branch_name: str, ticket_id: str, title: str, body: str) -> Optional[str]:
        """
        Create a pull request for a bug fix
        
        Args:
            branch_name: The name of the branch to create the PR from
            ticket_id: The JIRA ticket ID
            title: The title of the pull request
            body: The body of the pull request
            
        Returns:
            str: The URL of the pull request if successful, None otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot create pull request")
            return None
            
        try:
            repo = self.client.get_repo(self.default_repo)
            
            # Check if a PR already exists for this branch
            pulls = repo.get_pulls(state='open', head=branch_name)
            if pulls.totalCount > 0:
                pr = pulls[0]
                logger.info(f"PR already exists for branch {branch_name}: {pr.html_url}")
                return pr.html_url
            
            # Create the pull request
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=self.default_branch
            )
            
            logger.info(f"Pull request created successfully: {pr.html_url}")
            return pr.html_url
        except GithubException as e:
            logger.error(f"GitHub error creating pull request: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating pull request: {str(e)}")
            return None
    
    def add_pr_comment(self, pr_number: Union[int, str], comment: str) -> bool:
        """
        Add a comment to a pull request
        
        Args:
            pr_number: The number of the pull request
            comment: The comment to add
            
        Returns:
            bool: True if comment was added successfully, False otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot add comment")
            return False
            
        try:
            repo = self.client.get_repo(self.default_repo)
            pull = repo.get_pull(int(pr_number))  # pr_number must be an integer
            pull.create_issue_comment(comment)
            logger.info(f"Comment added to pull request #{pr_number} successfully")
            return True
        except GithubException as e:
            logger.error(f"GitHub error adding comment: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error adding comment: {str(e)}")
            return False

    def check_for_existing_pr(self, branch_name: str, base_branch: str) -> Optional[Dict[str, Any]]:
        """
        Check if a pull request already exists for a branch
        
        Args:
            branch_name: The name of the branch to check
            base_branch: The base branch of the pull request
            
        Returns:
            A dictionary containing the PR number and URL if a PR exists, None otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot check for existing PR")
            return None
        
        try:
            repo = self.client.get_repo(self.default_repo)
            pulls = repo.get_pulls(state='open', head=f"{repo.owner.login}:{branch_name}", base=base_branch)
            
            for pull in pulls:
                logger.info(f"Found existing PR for branch {branch_name}: {pull.html_url}")
                return {
                    "number": pull.number,
                    "url": pull.html_url,
                    "title": pull.title,
                    "state": pull.state
                }
            
            return None
        except GithubException as e:
            logger.error(f"GitHub error checking for existing PR: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error checking for existing PR: {str(e)}")
            return None

    def apply_file_changes_from_gpt(self, branch_name: str, file_path: str, gpt_response: str, ticket_id: str) -> bool:
        """
        Apply file changes from GPT response
        
        Args:
            branch_name: The name of the branch to commit to
            file_path: The path to the file to change
            gpt_response: The GPT response containing the changes
            ticket_id: The JIRA ticket ID
            
        Returns:
            bool: True if commit was successful, False otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot apply file changes")
            return False
            
        try:
            repo = self.client.get_repo(self.default_repo)
            
            # Extract the code block for the file from the GPT response
            file_pattern = re.compile(rf'---FILE: {re.escape(file_path)}---(.*?)---END FILE---', re.DOTALL)
            match = file_pattern.search(gpt_response)
            
            if not match:
                logger.warning(f"No code block found for file {file_path} in GPT response")
                return False
            
            code_block = match.group(1).strip()
            
            # Get the file content
            contents = repo.get_contents(file_path, ref=branch_name)
            original_content = contents.decoded_content.decode('utf-8')
            
            # Replace the file content with the code block
            updated_content = code_block
            
            # Commit the changes
            commit_message = f"Fix {ticket_id}: Apply GPT-suggested changes to {file_path}"
            commit = repo.update_file(
                path=file_path,
                message=commit_message,
                content=updated_content,
                sha=contents.sha,
                branch=branch_name
            )
            
            logger.info(f"Changes committed to file {file_path} in branch {branch_name} successfully")
            return True
        except GithubException as e:
            logger.error(f"GitHub error applying file changes: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error applying file changes: {str(e)}")
            return False

    def check_file_exists(self, file_path: str, branch: str = None) -> bool:
        """
        Check if a file exists in the repository
        
        Args:
            file_path: Path to the file
            branch: Branch to check (defaults to default_branch)
            
        Returns:
            bool: True if file exists, False otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot check if file exists")
            return False
            
        branch = branch or self.default_branch
        
        try:
            repo = self.client.get_repo(self.default_repo)
            contents = repo.get_contents(file_path, ref=branch)
            return True
        except GithubException as e:
            if e.status == 404:
                return False
            logger.error(f"GitHub error checking file existence: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error checking if file exists: {str(e)}")
            return False

    def validate_patch(self, file_path: str, diff_content: str) -> Dict[str, Any]:
        """
        Validate if a patch can be applied to a file
        
        Args:
            file_path: Path to the file to patch
            diff_content: Diff content to apply
            
        Returns:
            Dict with validation results:
                valid: Boolean indicating if patch is valid
                reasons: List of rejection reasons if invalid
                confidence_boost: Optional confidence boost if valid
                confidence_penalty: Optional confidence penalty if invalid
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot validate patch")
            return {"valid": False, "reasons": ["GitHub client not initialized"], "confidence_penalty": 20}
        
        # Check if file exists
        file_exists = self.check_file_exists(file_path)
        if not file_exists:
            return {
                "valid": False, 
                "reasons": [f"File {file_path} does not exist in repository"], 
                "confidence_penalty": 25
            }
        
        # Check for placeholders in file path or diff
        placeholder_patterns = [
            r'/path/to/',
            r'example\.com',
            r'YOUR_',
            r'<placeholder>',
            r'path/to/',
            r'some/file',
            r'my_file\.py',
            r'your_',
            r'TODO:',
            r'FIXME:'
        ]
        
        for pattern in placeholder_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return {
                    "valid": False, 
                    "reasons": ["Placeholder detected in file path"], 
                    "confidence_penalty": 30
                }
            if re.search(pattern, diff_content, re.IGNORECASE):
                return {
                    "valid": False, 
                    "reasons": ["Placeholder detected in diff content"], 
                    "confidence_penalty": 25
                }
        
        # Basic diff syntax validation
        if not re.search(r'@@\s+\-\d+,\d+\s+\+\d+,\d+\s+@@', diff_content) and not ('+' in diff_content or '-' in diff_content):
            return {
                "valid": False, 
                "reasons": ["Invalid diff syntax"], 
                "confidence_penalty": 20
            }
        
        # For a more thorough validation, we could try to apply the patch to a temp file
        try:
            # Get the current file content
            repo = self.client.get_repo(self.default_repo)
            file_content = repo.get_contents(file_path, ref=self.default_branch).decoded_content.decode('utf-8')
            
            # Create a temporary file with the content
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(file_content)
            
            # Create a temporary patch file
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as patch_file:
                patch_file_path = patch_file.name
                patch_file.write(diff_content)
            
            # Try to apply the patch
            try:
                result = subprocess.run(
                    ['patch', '--dry-run', '-f', '-s', temp_file_path, patch_file_path],
                    capture_output=True,
                    text=True,
                    timeout=5  # Timeout after 5 seconds
                )
                
                # Clean up temporary files
                os.unlink(temp_file_path)
                os.unlink(patch_file_path)
                
                if result.returncode != 0:
                    return {
                        "valid": False,
                        "reasons": ["Patch does not apply cleanly", result.stderr.strip()],
                        "confidence_penalty": 15
                    }
                
                return {
                    "valid": True,
                    "reasons": [],
                    "confidence_boost": 10
                }
            except subprocess.TimeoutExpired:
                # Clean up temporary files
                os.unlink(temp_file_path)
                os.unlink(patch_file_path)
                
                return {
                    "valid": False,
                    "reasons": ["Patch validation timed out"],
                    "confidence_penalty": 10
                }
        except Exception as e:
            logger.error(f"Error validating patch: {str(e)}")
            
            # Default to passing validation if we can't do a thorough check
            # but with a small confidence boost
            return {
                "valid": True,
                "reasons": ["Basic validation passed, but detailed validation failed"],
                "confidence_boost": 5
            }

    def find_pr_for_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Find pull requests related to a ticket ID
        
        Args:
            ticket_id: The JIRA ticket ID
            
        Returns:
            Optional dict with PR info if found, None otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot find PR")
            return None
            
        try:
            repo = self.client.get_repo(self.default_repo)
            
            # Try different branch name patterns
            branch_names = [
                f"fix/{ticket_id}", 
                f"fix/{ticket_id.lower()}", 
                f"bugfix/{ticket_id}",
                f"bugfix/{ticket_id.lower()}"
            ]
            
            for branch_name in branch_names:
                try:
                    # Try to find a PR for this branch
                    pulls = repo.get_pulls(state='open', head=f"{repo.owner.login}:{branch_name}")
                    pull_list = list(pulls)
                    
                    if pull_list:
                        pr = pull_list[0]  # Get the first matching PR
                        return {
                            "number": pr.number,
                            "url": pr.html_url,
                            "title": pr.title,
                            "state": pr.state,
                            "branch": branch_name
                        }
                except GithubException:
                    continue
                    
            # Also search by PR title/body containing ticket ID
            open_pulls = repo.get_pulls(state='open')
            for pr in open_pulls:
                if ticket_id in pr.title or ticket_id in pr.body:
                    return {
                        "number": pr.number,
                        "url": pr.html_url,
                        "title": pr.title,
                        "state": pr.state,
                        "branch": pr.head.ref
                    }
                    
            return None
        except Exception as e:
            logger.error(f"Error finding PR for ticket {ticket_id}: {str(e)}")
            return None

    def find_pr_for_branch(self, branch_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a pull request for a specific branch name
        
        Args:
            branch_name: The name of the branch
            
        Returns:
            Optional dict with PR info if found, None otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot find PR")
            return None
            
        try:
            repo = self.client.get_repo(self.default_repo)
            
            # Try to find a PR for this branch
            pulls = repo.get_pulls(state='open', head=f"{repo.owner.login}:{branch_name}")
            pull_list = list(pulls)
            
            if pull_list:
                pr = pull_list[0]  # Get the first matching PR
                return {
                    "number": pr.number,
                    "url": pr.html_url,
                    "title": pr.title,
                    "state": pr.state,
                    "branch": branch_name
                }
            
            return None
        except Exception as e:
            logger.error(f"Error finding PR for branch {branch_name}: {str(e)}")
            return None

    def delete_branch(self, branch_name: str) -> bool:
        """
        Delete a branch from the repository
        
        Args:
            branch_name: The name of the branch to delete
            
        Returns:
            bool: True if the branch was successfully deleted, False otherwise
        """
        if not self.client:
            logger.warning("GitHub client not initialized, cannot delete branch")
            return False
        
        try:
            repo = self.client.get_repo(self.default_repo)
            ref = repo.get_git_ref(f"refs/heads/{branch_name}")
            ref.delete()
            logger.info(f"Successfully deleted branch {branch_name}")
            return True
        except GithubException as e:
            logger.error(f"GitHub error deleting branch {branch_name}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error deleting branch {branch_name}: {str(e)}")
            return False
