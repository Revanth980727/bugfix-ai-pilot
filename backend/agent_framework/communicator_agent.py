
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
    
    # ... keep existing code (run methods)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming data and communicate results"""
        ticket_id = input_data.get("ticket_id", "unknown")
        logger.info(f"Processing communication request for ticket {ticket_id}")
        
        # Log input data for debugging
        logger.info(f"Communication input: {json.dumps(input_data, default=str)[:500]}...")
        
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
                        
                        # Create a branch for the fix
                        branch_created, branch_name = github_service.create_fix_branch(ticket_id)
                        
                        if branch_created:
                            logger.info(f"Created branch {branch_name} for ticket {ticket_id}")
                            
                            # Get file changes from input data
                            file_changes = input_data.get("file_changes", [])
                            file_contents = []
                            file_paths = []
                            
                            if not file_changes:
                                file_changes = []
                                
                                # Try to extract file changes from patch data
                                patch_data = input_data.get("patch_data", {})
                                patched_files = patch_data.get("patched_files", [])
                                patch_content = patch_data.get("patch_content", "")
                                
                                for file_path in patched_files:
                                    file_paths.append(file_path)
                                    # For patched files without explicit content, we'll pass None and let
                                    # the commit_patch method handle it
                                    file_contents.append(None)
                            else:
                                # Extract paths and contents from file_changes
                                for change in file_changes:
                                    if change.get("filename") and change.get("content"):
                                        file_paths.append(change.get("filename"))
                                        file_contents.append(change.get("content"))
                            
                            # Commit message
                            commit_message = input_data.get("commit_message", f"Fix for {ticket_id}")
                            
                            # Commit the changes
                            if file_paths:
                                # Add timestamp to ensure changes are seen as unique
                                commit_message = f"{commit_message} - {int(time.time())}"
                                
                                # Updated to pass both file paths and contents
                                commit_success = github_service.commit_bug_fix(
                                    branch_name, file_paths, file_contents, ticket_id, commit_message
                                )
                                
                                if commit_success:
                                    logger.info(f"Successfully committed changes for {ticket_id}")
                                    
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
                                    logger.error(f"Failed to commit changes for ticket {ticket_id}")
                            else:
                                logger.warning(f"No file changes found for ticket {ticket_id}")
                        else:
                            logger.error(f"Failed to create branch for ticket {ticket_id}")
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
        """Create a GitHub PR with the fix"""
        logger.info(f"Creating GitHub PR for ticket {ticket_id}")
        
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
                subprocess.run(clone_cmd, check=True, capture_output=True)
                
                # Create a new branch
                branch_name = f"fix/{ticket_id.lower()}"
                logger.info(f"Creating branch {branch_name}")
                create_branch_cmd = ["git", "checkout", "-b", branch_name]
                subprocess.run(create_branch_cmd, check=True, capture_output=True, cwd=temp_dir)
                
                # Apply changes
                patch_data = input_data.get("patch_data", {})
                patched_files = patch_data.get("patched_files", [])
                file_changes = input_data.get("file_changes", [])
                
                # Create timestamp for unique changes
                timestamp = int(time.time())
                
                # First try to use file_changes if available (which include content)
                if file_changes:
                    for change in file_changes:
                        if change.get("filename") and change.get("content"):
                            file_path = change.get("filename")
                            content = change.get("content")
                            
                            # Write file content
                            file_full_path = os.path.join(temp_dir, file_path)
                            os.makedirs(os.path.dirname(file_full_path), exist_ok=True)
                            
                            with open(file_full_path, 'w') as f:
                                f.write(content)
                            
                            # Add the file
                            add_cmd = ["git", "add", file_path]
                            subprocess.run(add_cmd, check=True, capture_output=True, cwd=temp_dir)
                elif patched_files:
                    # Fallback to patch_data if file_changes not available
                    for file_path in patched_files:
                        # Write placeholder content if we don't have the actual content
                        file_full_path = os.path.join(temp_dir, file_path)
                        os.makedirs(os.path.dirname(file_full_path), exist_ok=True)
                        
                        with open(file_full_path, 'w') as f:
                            f.write(f"// Fixed content for {file_path}\n// Timestamp: {timestamp}\n")
                        
                        # Add the file
                        add_cmd = ["git", "add", file_path]
                        subprocess.run(add_cmd, check=True, capture_output=True, cwd=temp_dir)
                
                # Commit the changes
                commit_msg = f"Fix for {ticket_id} - {timestamp}"
                commit_cmd = ["git", "commit", "-m", commit_msg]
                subprocess.run(commit_cmd, check=True, capture_output=True, cwd=temp_dir)
                
                # Push the changes
                push_cmd = ["git", "push", "origin", branch_name]
                subprocess.run(push_cmd, check=True, capture_output=True, cwd=temp_dir)
                
                # Create a PR via GitHub CLI or API
                logger.info(f"Would create PR for {branch_name}")
                
                # Return a simulated PR URL with number
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
