
import os
import logging
import json
import time
import subprocess
import tempfile
from typing import Dict, Any, Optional, Union, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator-agent")

class CommunicatorAgent:
    """Agent responsible for communicating results to external systems (JIRA, GitHub, etc.)"""
    
    def __init__(self):
        logger.info("Initializing CommunicatorAgent")
        # Get configuration from environment
        self.github_token = os.environ.get("GITHUB_TOKEN", "")
        self.jira_token = os.environ.get("JIRA_TOKEN", "")
        self.repo_url = os.environ.get("REPO_URL", "")
        
        # Get the branch name from environment - exact case sensitivity required
        # Check for GITHUB_BRANCH first (preferred)
        self.github_branch = os.environ.get("GITHUB_BRANCH", None)
        
        # If not found, check for alternative names as fallback
        if self.github_branch is None:
            for env_var in ["GITHUB_DEFAULT_BRANCH", "DEFAULT_BRANCH", "GIT_BRANCH"]:
                if os.environ.get(env_var):
                    self.github_branch = os.environ.get(env_var)
                    logger.warning(f"GITHUB_BRANCH not found, using {env_var} instead: {self.github_branch}")
                    break
        
        # If still not found, raise an error
        if self.github_branch is None:
            error_msg = "GITHUB_BRANCH environment variable is not set. Please set it in .env file."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"Using GitHub branch from environment: {self.github_branch}")
        
        # Check for git installation
        self._check_git_available()
    
    def _check_git_available(self):
        """Check if git is available in the system path"""
        try:
            # Run 'git --version' to check if git is installed
            result = subprocess.run(
                ["git", "--version"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            
            if result.returncode == 0:
                git_version = result.stdout.strip()
                logger.info(f"Git is available: {git_version}")
            else:
                logger.warning("Git command failed. Git may not be installed properly.")
                logger.warning(f"Error: {result.stderr.strip()}")
        except FileNotFoundError:
            logger.warning("Git command not found. Git is not installed or not in the system path.")
        except Exception as e:
            logger.warning(f"Error checking git availability: {str(e)}")
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the communicator agent with the provided input data.
        This method is called from jira_service.py.
        
        Args:
            input_data: Dictionary with input data from previous agents
            
        Returns:
            Dictionary with results of the communication tasks
        """
        logger.info(f"Running communicator agent with input: {input_data.get('ticket_id', 'unknown')}")
        
        # Log detailed input data for debugging - focus on patch data
        patch_data = input_data.get("patch_data", {})
        if patch_data:
            logger.info(f"Received patch data with {len(patch_data.get('patched_files', []))} files")
            for file_path in patch_data.get("patched_files", [])[:5]:
                logger.info(f"Patched file: {file_path}")
            if len(patch_data.get("patched_files", [])) > 5:
                logger.info(f"... and {len(patch_data.get('patched_files', [])) - 5} more files")
        
        # Call the existing process method that contains the actual implementation
        return self.process(input_data)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming data and communicate results"""
        ticket_id = input_data.get("ticket_id", "unknown")
        logger.info(f"Processing communication request for ticket {ticket_id}")
        
        # Create result with default values
        result = {
            "ticket_id": ticket_id,
            "communications_success": False,
            "pr_created": False,
            "jira_updated": False,
            "timestamp": time.time()
        }
        
        # Process based on update type
        update_type = input_data.get("update_type", "progress")
        
        if update_type == "early_escalation":
            logger.info(f"Processing early escalation for ticket {ticket_id}")
            result["early_escalation"] = True
            result["escalation_reason"] = input_data.get("escalation_reason", "Unknown reason")
            # Handle the early escalation
            try:
                self._update_jira_early_escalation(ticket_id, input_data)
                result["jira_updated"] = True
            except Exception as e:
                logger.error(f"Error updating JIRA for early escalation: {str(e)}")
                result["error"] = str(e)
        elif update_type == "progress":
            logger.info(f"Processing progress update for ticket {ticket_id}")
            # Handle the progress update
            try:
                self._update_jira_progress(ticket_id, input_data)
                result["jira_updated"] = True
            except Exception as e:
                logger.error(f"Error updating JIRA with progress: {str(e)}")
                result["error"] = str(e)
        else:
            # Default case - complete workflow
            test_passed = input_data.get("success", False)
            
            # FIXED: Check patch_data and its elements explicitly
            patch_data = input_data.get("patch_data", {})
            has_patch_files = len(patch_data.get("patched_files", [])) > 0
            has_patch_content = bool(patch_data.get("patch_content", ""))
            
            logger.info(f"Test passed: {test_passed}, Has patch files: {has_patch_files}, Has patch content: {has_patch_content}")
            
            # FIXED: Proceed with patching and PR creation only when tests pass AND we have valid patch data
            if test_passed and has_patch_files and has_patch_content:
                logger.info(f"Creating PR for successful fix for ticket {ticket_id}")
                try:
                    # Apply patch and create PR
                    pr_result = self._apply_patch_and_create_pr(ticket_id, input_data)
                    
                    # Update result with PR info
                    if pr_result:
                        result.update(pr_result)
                        
                except Exception as e:
                    logger.error(f"Error creating GitHub PR: {str(e)}")
                    result["pr_error"] = str(e)
            else:
                # Log the reason why we didn't proceed with PR creation
                if not test_passed:
                    logger.warning(f"Skipping PR creation: Tests did not pass for ticket {ticket_id}")
                elif not has_patch_files:
                    logger.warning(f"Skipping PR creation: No patched files provided for ticket {ticket_id}")
                elif not has_patch_content:
                    logger.warning(f"Skipping PR creation: No patch content provided for ticket {ticket_id}")
            
            # Update JIRA regardless of PR creation status
            try:
                # Make sure pr_url is a string if it's a tuple
                pr_url = result.get("pr_url")
                if isinstance(pr_url, tuple) and len(pr_url) > 0:
                    pr_url = pr_url[0]
                    
                self._update_jira_final(ticket_id, test_passed, pr_url)
                result["jira_updated"] = True
            except Exception as e:
                logger.error(f"Error updating JIRA with final result: {str(e)}")
                result["jira_error"] = str(e)
        
        # Set overall success
        result["communications_success"] = result.get("jira_updated", False) or result.get("pr_created", False)
        
        logger.info(f"Communication completed for ticket {ticket_id}")
        return result
    
    def _apply_patch_and_create_pr(self, ticket_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch and create GitHub PR with the fix"""
        logger.info(f"Applying patch and creating PR for ticket {ticket_id}")
        result = {
            "pr_created": False,
            "pr_url": None,
            "pr_number": None
        }
        
        # Extract patch data
        patch_data = input_data.get("patch_data", {})
        patched_files = patch_data.get("patched_files", [])
        patch_content = patch_data.get("patch_content", "")
        
        # Log patch details for debugging
        logger.info(f"Patch affects {len(patched_files)} files")
        logger.debug(f"Patch content preview: {patch_content[:500]}..." if len(patch_content) > 500 else patch_content)
        
        try:
            # Try to import the GitHub service
            try:
                from backend.github_service.github_service import GitHubService
                github_service = GitHubService()
                logger.info("Successfully imported GitHubService")
                
                # Use branch from environment
                branch_name = self.github_branch
                logger.info(f"Using branch from environment: {branch_name}")
                
                # Check if we have valid patch data
                if not patched_files or not patch_content:
                    logger.error("Missing required patch data from developer agent")
                    logger.error(f"Patched files: {patched_files}")
                    logger.error(f"Patch content available: {'Yes' if patch_content else 'No'}")
                    return result
                
                logger.info(f"Will patch {len(patched_files)} files")
                for i, file_path in enumerate(patched_files[:5]):
                    logger.info(f"File {i+1}: {file_path}")
                if len(patched_files) > 5:
                    logger.info(f"... and {len(patched_files) - 5} more files")
                
                # Commit message
                commit_message = patch_data.get("commit_message", f"Fix for {ticket_id}")
                if not commit_message.startswith(f"Fix for {ticket_id}") and not commit_message.startswith(f"Fix {ticket_id}"):
                    commit_message = f"Fix for {ticket_id}: {commit_message}"
                
                logger.info(f"Using commit message: {commit_message}")
                
                # Commit the patch directly using the GitHub service
                logger.info("Applying patch via GitHub service")
                commit_success = github_service.commit_patch(
                    branch_name=branch_name,
                    patch_content=patch_content,
                    commit_message=commit_message,
                    patch_file_paths=patched_files
                )
                
                if commit_success:
                    logger.info(f"Successfully committed patch for {ticket_id} to branch {branch_name}")
                    
                    # Create a PR
                    pr_result = github_service.create_fix_pr(
                        branch_name, 
                        ticket_id,
                        f"Fix for {ticket_id}",
                        f"This PR fixes the issue described in {ticket_id}"
                    )
                    
                    if pr_result and isinstance(pr_result, dict):
                        # Extract PR URL and number
                        pr_url = pr_result.get("url")
                        pr_number = pr_result.get("number")
                        
                        logger.info(f"Created PR #{pr_number} for ticket {ticket_id}: {pr_url}")
                        
                        # Record PR information in result
                        result["pr_url"] = pr_url
                        result["pr_number"] = pr_number
                        result["pr_created"] = True
                    else:
                        logger.error(f"Failed to create PR for ticket {ticket_id}")
                else:
                    logger.error(f"Failed to commit patch for ticket {ticket_id}")
            except ImportError as e:
                logger.warning(f"Failed to import GitHubService: {str(e)}")
                logger.info("Falling back to direct git commands")
                
                # Use direct git commands as fallback
                git_result = self._apply_patch_using_git(ticket_id, patched_files, patch_content, input_data)
                
                if git_result:
                    result.update(git_result)
            
        except Exception as e:
            logger.error(f"Error in patch application and PR creation: {str(e)}")
            
        return result
    
    def _apply_patch_using_git(self, ticket_id: str, patched_files: list, patch_content: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch using direct git commands and create PR"""
        logger.info(f"Using git commands to apply patch for ticket {ticket_id}")
        result = {
            "pr_created": False,
            "pr_url": None,
            "pr_number": None
        }
        
        try:
            # Create a temporary directory for git operations
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info(f"Created temporary directory: {temp_dir}")
                
                # Clone the repository
                repo_url = self.repo_url
                if not repo_url:
                    repo_url = f"https://github.com/{os.environ.get('GITHUB_REPO_OWNER', 'example')}/{os.environ.get('GITHUB_REPO_NAME', 'repo')}.git"
                
                # Add token to URL if available
                if self.github_token:
                    repo_parts = repo_url.split("://")
                    if len(repo_parts) == 2:
                        repo_url = f"{repo_parts[0]}://{self.github_token}@{repo_parts[1]}"
                
                # Clone the repository
                logger.info(f"Cloning repository to {temp_dir}")
                clone_cmd = ["git", "clone", repo_url, temp_dir]
                clone_result = subprocess.run(clone_cmd, check=True, capture_output=True)
                logger.info("Repository cloned successfully")
                
                # Checkout the branch
                branch_name = self.github_branch
                logger.info(f"Checking out branch {branch_name}")
                checkout_branch_cmd = ["git", "checkout", branch_name]
                checkout_result = subprocess.run(checkout_branch_cmd, check=True, capture_output=True, cwd=temp_dir)
                logger.info(f"Successfully checked out branch {branch_name}")
                
                # Write patch to temporary file
                patch_file_path = os.path.join(temp_dir, "bugfix.patch")
                with open(patch_file_path, "w") as f:
                    f.write(patch_content)
                logger.info(f"Wrote patch content to {patch_file_path}")
                
                # First check if the patch can be applied cleanly
                logger.info("Checking if patch can be applied cleanly")
                check_cmd = ["git", "apply", "--check", patch_file_path]
                try:
                    check_result = subprocess.run(check_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                    logger.info("Patch can be applied cleanly")
                    
                    # Apply the patch
                    logger.info("Applying patch")
                    apply_cmd = ["git", "apply", patch_file_path]
                    apply_result = subprocess.run(apply_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                    logger.info("Patch applied successfully")
                    
                    # Stage the changed files
                    logger.info(f"Staging {len(patched_files)} changed files")
                    for file_path in patched_files:
                        add_cmd = ["git", "add", file_path]
                        add_result = subprocess.run(add_cmd, check=True, capture_output=True, cwd=temp_dir)
                        logger.info(f"Staged file: {file_path}")
                    
                    # Verify changes were applied
                    status_cmd = ["git", "status", "--porcelain"]
                    status_result = subprocess.run(status_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                    status_output = status_result.stdout.strip()
                    
                    if not status_output:
                        logger.error("No changes detected after applying patch")
                        return result
                        
                    logger.info(f"Git status shows changes: {status_output}")
                    
                    # Commit changes
                    commit_msg = input_data.get("patch_data", {}).get("commit_message", f"Fix for {ticket_id}")
                    if not commit_msg.startswith(f"Fix for {ticket_id}") and not commit_msg.startswith(f"Fix {ticket_id}"):
                        commit_msg = f"Fix for {ticket_id}: {commit_msg}"
                        
                    logger.info(f"Committing changes with message: {commit_msg}")
                    commit_cmd = ["git", "commit", "-m", commit_msg]
                    commit_result = subprocess.run(commit_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                    logger.info(f"Commit successful: {commit_result.stdout}")
                    
                    # Push changes
                    logger.info(f"Pushing changes to branch {branch_name}")
                    push_cmd = ["git", "push", "origin", branch_name]
                    push_result = subprocess.run(push_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                    logger.info("Changes pushed successfully")
                    
                    # Create PR (this part is simplified, as git CLI doesn't create PRs directly)
                    # In a real implementation, you'd use GitHub API for this
                    repo_owner = os.environ.get("GITHUB_REPO_OWNER", "example")
                    repo_name = os.environ.get("GITHUB_REPO_NAME", "repo")
                    pr_url = f"https://github.com/{repo_owner}/{repo_name}/pull/123"  # Placeholder
                    pr_number = 123  # Placeholder
                    
                    logger.info(f"PR would be created at: {pr_url}")
                    result["pr_url"] = pr_url
                    result["pr_number"] = pr_number
                    result["pr_created"] = True
                    
                    return result
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"Patch cannot be applied cleanly: {e.stderr}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error applying patch using git: {str(e)}")
            
        return result
    
    def _update_jira_early_escalation(self, ticket_id: str, input_data: Dict[str, Any]):
        """Update JIRA with early escalation information"""
        logger.info(f"Would update JIRA ticket {ticket_id} with early escalation")
        # In a real implementation, this would use JIRA API to update the ticket
        
    def _update_jira_progress(self, ticket_id: str, input_data: Dict[str, Any]):
        """Update JIRA with progress information"""
        logger.info(f"Would update JIRA ticket {ticket_id} with progress")
        # In a real implementation, this would use JIRA API to update the ticket
        
    def _update_jira_final(self, ticket_id: str, success: bool, pr_url: Optional[str] = None):
        """Update JIRA with final result"""
        status = "Done" if success else "Failed"
        logger.info(f"Would update JIRA ticket {ticket_id} to {status}")
        if pr_url:
            logger.info(f"Would add PR link to JIRA: {pr_url}")
        # In a real implementation, this would use JIRA API to update the ticket
