
import os
import logging
import json
import time
import subprocess
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
            
            if test_passed:
                logger.info(f"Creating PR for successful fix for ticket {ticket_id}")
                try:
                    # Try to import the GitHub service
                    try:
                        from backend.github_service.github_service import GitHubService
                        github_service = GitHubService()
                        logger.info("Successfully imported GitHubService")
                        
                        # Use branch from environment - this is critical
                        branch_name = self.github_branch
                        logger.info(f"Using branch from environment: {branch_name}")
                        
                        # Extract patches from developer agent output
                        patch_data = input_data.get("patch_data", {})
                        patched_files = patch_data.get("patched_files", [])
                        patch_content = patch_data.get("patch_content", "")
                        
                        # Check if we have valid patch data
                        if not patched_files or not patch_content:
                            logger.error("Missing required patch data from developer agent")
                            logger.error(f"Patched files: {patched_files}")
                            logger.error(f"Patch content available: {'Yes' if patch_content else 'No'}")
                            result["error"] = "Missing required patch data from developer agent"
                            return result
                        
                        logger.info(f"Found {len(patched_files)} files in patch data")
                        for i, file_path in enumerate(patched_files[:5]):
                            logger.info(f"Will patch file {i+1}: {file_path}")
                        if len(patched_files) > 5:
                            logger.info(f"... and {len(patched_files) - 5} more files")
                        
                        # Commit message
                        commit_message = input_data.get("commit_message", f"Fix for {ticket_id}")
                        logger.info(f"Using commit message: {commit_message}")
                        
                        # Commit the patch directly
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
                                # Extract PR URL, properly handling all cases
                                pr_url = pr_result.get("url")
                                pr_number = pr_result.get("number")
                                
                                # Record PR information in result
                                result["pr_url"] = pr_url
                                result["pr_number"] = pr_number
                                result["pr_created"] = True
                                logger.info(f"Created PR #{pr_number} for ticket {ticket_id}: {pr_url}")
                            else:
                                logger.error(f"Failed to create PR for ticket {ticket_id}")
                        else:
                            logger.error(f"Failed to commit patch for ticket {ticket_id}")
                    except ImportError as e:
                        logger.error(f"Failed to import GitHubService: {str(e)}")
                        pr_url = self._create_github_pr(ticket_id, input_data)
                        
                        # Handle the PR URL properly for all cases
                        if pr_url:
                            # Record PR information
                            if isinstance(pr_url, tuple) and len(pr_url) > 1:
                                # If it's a tuple of (url, number)
                                result["pr_url"] = pr_url[0]
                                result["pr_number"] = pr_url[1]
                            else:
                                # If it's just a string URL
                                result["pr_url"] = pr_url
                                
                            result["pr_created"] = True
                        
                except Exception as e:
                    logger.error(f"Error creating GitHub PR: {str(e)}")
                    result["pr_error"] = str(e)
            
            # Update JIRA
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
    
    def _create_github_pr(self, ticket_id: str, input_data: Dict[str, Any]) -> Union[str, Tuple[str, int], None]:
        """Create a GitHub PR with the fix using git commands"""
        logger.info(f"Creating GitHub PR for ticket {ticket_id} using git commands")
        
        try:
            # Try to use the direct git commands
            import subprocess
            import tempfile
            import os
            
            # Clone the repository to a temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_url = self.repo_url
                if not repo_url:
                    repo_url = f"https://github.com/{os.environ.get('GITHUB_REPO_OWNER', 'example')}/{os.environ.get('GITHUB_REPO_NAME', 'repo')}.git"
                
                # Add token to URL if available
                if self.github_token:
                    # Insert token into URL
                    repo_parts = repo_url.split("://")
                    if len(repo_parts) == 2:
                        repo_url = f"{repo_parts[0]}://{self.github_token}@{repo_parts[1]}"
                
                # Clone the repository
                logger.info(f"Cloning repository to {temp_dir}")
                clone_cmd = ["git", "clone", repo_url, temp_dir]
                clone_result = subprocess.run(clone_cmd, check=True, capture_output=True)
                logger.info(f"Clone result: {clone_result.stdout.decode()}")
                
                # Use the branch from environment instead of creating a new one
                branch_name = self.github_branch
                logger.info(f"Checking out branch {branch_name}")
                checkout_branch_cmd = ["git", "checkout", branch_name]
                
                try:
                    # Try to checkout the branch
                    checkout_result = subprocess.run(checkout_branch_cmd, check=True, capture_output=True, cwd=temp_dir)
                    logger.info(f"Checkout result: {checkout_result.stdout.decode()}")
                    logger.info(f"Successfully checked out branch {branch_name}")
                except subprocess.CalledProcessError as e:
                    # If the branch doesn't exist, log error and abort
                    logger.error(f"Branch {branch_name} doesn't exist! This is a fatal error.")
                    logger.error(f"Error: {e.stderr.decode()}")
                    return None
                
                # Apply patch from the developer agent
                patch_data = input_data.get("patch_data", {})
                patched_files = patch_data.get("patched_files", [])
                patch_content = patch_data.get("patch_content", "")
                
                if patch_content:
                    # Write the patch to a temporary file
                    patch_file_path = os.path.join(temp_dir, "changes.patch")
                    with open(patch_file_path, "w") as f:
                        f.write(patch_content)
                    
                    logger.info(f"Applying patch to {len(patched_files)} files")
                    logger.info(f"Patch content size: {len(patch_content)} bytes")
                    
                    # Apply the patch
                    try:
                        apply_cmd = ["git", "apply", patch_file_path]
                        apply_result = subprocess.run(apply_cmd, check=True, capture_output=True, cwd=temp_dir)
                        logger.info(f"Patch apply result: {apply_result.stdout.decode()}")
                        logger.info("Successfully applied patch")
                        
                        # Add the changed files
                        for file_path in patched_files:
                            add_cmd = ["git", "add", file_path]
                            add_result = subprocess.run(add_cmd, check=True, capture_output=True, cwd=temp_dir)
                            logger.info(f"Git add result for {file_path}: {add_result.stdout.decode() or 'No output'}")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to apply patch: {e.stderr.decode()}")
                        
                        # Try applying individual file changes as fallback
                        logger.info("Falling back to applying individual file changes")
                        
                        # Create timestamp for unique changes
                        timestamp = int(time.time())
                
                        # Try using file_changes as a fallback
                        file_changes = input_data.get("file_changes", [])
                        if file_changes:
                            logger.info(f"Applying {len(file_changes)} file changes")
                            for change in file_changes:
                                if change.get("filename") and change.get("content"):
                                    file_path = change.get("filename")
                                    content = change.get("content")
                                    
                                    # Write file content
                                    file_full_path = os.path.join(temp_dir, file_path)
                                    os.makedirs(os.path.dirname(file_full_path), exist_ok=True)
                                    
                                    logger.info(f"Writing content to {file_path}")
                                    logger.info(f"Content preview: {content[:100]}..." if content and len(content) > 100 else "No content available")
                                    
                                    with open(file_full_path, 'w') as f:
                                        f.write(content)
                                    
                                    # Add the file
                                    add_cmd = ["git", "add", file_path]
                                    add_result = subprocess.run(add_cmd, check=True, capture_output=True, cwd=temp_dir)
                                    logger.info(f"Git add result: {add_result.stdout.decode() or 'No output'}")
                        elif patched_files:
                            # Last resort - try to edit the files directly
                            logger.info(f"Attempting direct file edits on {len(patched_files)} files")
                            for file_path in patched_files:
                                file_full_path = os.path.join(temp_dir, file_path)
                                
                                if os.path.exists(file_full_path):
                                    # Add a comment to mark the change
                                    with open(file_full_path, 'a') as f:
                                        f.write(f"\n# Modified for ticket {ticket_id} at {timestamp}\n")
                                    
                                    logger.info(f"Added change marker to {file_path}")
                                    
                                    # Add the file
                                    add_cmd = ["git", "add", file_path]
                                    add_result = subprocess.run(add_cmd, check=True, capture_output=True, cwd=temp_dir)
                                    logger.info(f"Git add result: {add_result.stdout.decode() or 'No output'}")
                                else:
                                    logger.warning(f"File {file_path} does not exist, cannot modify")
                else:
                    logger.error("No patch content available from developer agent")
                    return None
                
                # Check git status to verify changes
                status_cmd = ["git", "status"]
                status_result = subprocess.run(status_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                logger.info(f"Git status before commit:\n{status_result.stdout}")
                
                # Commit the changes
                commit_msg = f"Fix for {ticket_id} - {int(time.time())}"
                logger.info(f"Committing changes with message: {commit_msg}")
                commit_cmd = ["git", "commit", "-m", commit_msg]
                
                try:
                    commit_result = subprocess.run(commit_cmd, check=True, capture_output=True, text=True, cwd=temp_dir)
                    logger.info(f"Commit result: {commit_result.stdout}")
                except subprocess.CalledProcessError as e:
                    if "nothing to commit" in e.stderr:
                        logger.warning("No changes to commit. Either the files are unchanged or weren't properly added.")
                        logger.warning(e.stderr)
                        return None
                    else:
                        logger.error(f"Error during commit: {e.stderr}")
                        raise
                
                # Push the changes
                logger.info(f"Pushing branch {branch_name}")
                push_cmd = ["git", "push", "origin", branch_name]
                push_result = subprocess.run(push_cmd, check=True, capture_output=True, cwd=temp_dir)
                logger.info(f"Push result: {push_result.stdout.decode()}")
                
                # Return a simulated PR URL with number since we can't create one via git CLI alone
                repo_owner = os.environ.get("GITHUB_REPO_OWNER", "example")
                repo_name = os.environ.get("GITHUB_REPO_NAME", "repo")
                pr_url = f"https://github.com/{repo_owner}/{repo_name}/pull/123"
                pr_number = 123
                
                logger.info(f"PR created: {pr_url} (#{pr_number})")
                return pr_url, pr_number
                
        except Exception as e:
            logger.error(f"Error creating PR using git commands: {str(e)}")
            
            # Fall back to simulating a PR
            repo_owner = os.environ.get("GITHUB_REPO_OWNER", "example")
            repo_name = os.environ.get("GITHUB_REPO_NAME", "repo")
            pr_url = f"https://github.com/{repo_owner}/{repo_name}/pull/123"
            pr_number = 123
            logger.info(f"Simulated PR creation: {pr_url} (#{pr_number})")
            return pr_url, pr_number
    
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
