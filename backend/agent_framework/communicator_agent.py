
import os
import logging
import json
import time
import subprocess
import tempfile
import hashlib
from typing import Dict, Any, Optional, Union, Tuple, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator-agent")

class CommunicatorAgent:
    """Agent responsible for communicating results to external systems (JIRA, GitHub, etc.)"""
    
    def __init__(self, test_mode: bool = False):
        logger.info("Initializing CommunicatorAgent")
        # Get configuration from environment
        self.github_token = os.environ.get("GITHUB_TOKEN", "")
        self.jira_token = os.environ.get("JIRA_TOKEN", "")
        self.repo_url = os.environ.get("REPO_URL", "")
        self.test_mode = test_mode  # Flag to enable/disable test mode
        
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
    
    # ... keep existing code (_check_git_available and run methods)
    
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
            
            # Check patch_data and its elements explicitly
            patch_data = input_data.get("patch_data", {})
            has_patch_files = len(patch_data.get("patched_files", [])) > 0
            has_patch_content = bool(patch_data.get("patch_content", ""))
            
            logger.info(f"Test passed: {test_passed}, Has patch files: {has_patch_files}, Has patch content: {has_patch_content}")
            
            # Proceed with patching and PR creation only when tests pass AND we have valid patch data
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
        
        # Verify we have all needed patch data before proceeding
        if not patched_files or not patch_content:
            logger.error("Missing required patch data: either patched_files or patch_content is empty")
            return result
            
        try:
            # Try to import the GitHub service
            try:
                from backend.github_service.github_service import GitHubService
                github_service = GitHubService()
                logger.info("Successfully imported GitHubService")
                
                # Use branch from environment
                branch_name = self.github_branch
                logger.info(f"Using branch from environment: {branch_name}")
                
                # Commit message
                commit_message = patch_data.get("commit_message", f"Fix for {ticket_id}")
                if not commit_message.startswith(f"Fix for {ticket_id}") and not commit_message.startswith(f"Fix {ticket_id}"):
                    commit_message = f"Fix for {ticket_id}: {commit_message}"
                
                logger.info(f"Using commit message: {commit_message}")
                
                # Save patch content to a temporary file (for verification and fallback)
                with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as patch_file:
                    patch_file_path = patch_file.name
                    patch_file.write(patch_content)
                    logger.info(f"Wrote patch content to temporary file: {patch_file_path}")
                
                # Try to commit using GitHubService first
                logger.info("Attempting to commit via GitHubService")
                commit_success = github_service.commit_patch(
                    branch_name=branch_name,
                    patch_content=patch_content,
                    commit_message=commit_message,
                    patch_file_paths=patched_files
                )
                
                # If GitHubService commit fails or doesn't properly handle patches,
                # use our own implementation with git commands
                if not commit_success:
                    logger.warning("GitHubService commit_patch failed or didn't apply patch correctly")
                    logger.info("Falling back to direct git patch application")
                    
                    # Use our fallback patch application method
                    with tempfile.TemporaryDirectory() as temp_dir:
                        commit_success = self._apply_patch_directly(
                            patch_file_path=patch_file_path, 
                            patched_files=patched_files,
                            branch_name=branch_name,
                            commit_message=commit_message,
                            temp_dir=temp_dir
                        )
                else:
                    logger.info("GitHubService applied patch successfully")
                    
                    # Verify the changes were applied correctly by checking file checksums
                    self._verify_patch_application(patched_files, branch_name)
                
                # Clean up the temporary patch file
                try:
                    os.unlink(patch_file_path)
                    logger.info(f"Removed temporary patch file: {patch_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary patch file: {e}")
                
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
    
    def _verify_patch_application(self, patched_files: List[str], branch_name: str) -> None:
        """
        Verify that patch was correctly applied by checking file contents or checksums
        
        Args:
            patched_files: List of files that were patched
            branch_name: Branch where changes were applied
        """
        logger.info(f"Verifying patch application for {len(patched_files)} files")
        
        try:
            # Create a temporary directory to clone the repo for verification
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone the repo
                repo_url = self.repo_url
                if not repo_url:
                    repo_url = f"https://github.com/{os.environ.get('GITHUB_REPO_OWNER', 'example')}/{os.environ.get('GITHUB_REPO_NAME', 'repo')}.git"
                
                # Add token to URL if available
                if self.github_token:
                    repo_parts = repo_url.split("://")
                    if len(repo_parts) == 2:
                        repo_url = f"{repo_parts[0]}://{self.github_token}@{repo_parts[1]}"
                
                logger.info(f"Cloning repository to verify patch application")
                subprocess.run(
                    ["git", "clone", "--quiet", "--branch", branch_name, "--depth", "1", repo_url, temp_dir],
                    check=True, 
                    capture_output=True
                )
                
                # Check each patched file
                for file_path in patched_files:
                    full_path = os.path.join(temp_dir, file_path)
                    
                    if not os.path.exists(full_path):
                        logger.warning(f"Verification failed: File {file_path} does not exist after patch")
                        continue
                        
                    # Calculate file checksum for verification
                    with open(full_path, 'rb') as f:
                        file_content = f.read()
                        checksum = hashlib.md5(file_content).hexdigest()
                        
                    # Log file info and preview
                    logger.info(f"Verified file {file_path} exists after patch (checksum: {checksum})")
                    logger.debug(f"File content preview: {file_content[:200].decode('utf-8', errors='replace')}...")
                    
                logger.info("Patch verification completed")
                
        except Exception as e:
            logger.error(f"Error during patch verification: {str(e)}")
    
    def _apply_patch_directly(self, patch_file_path: str, patched_files: List[str], 
                             branch_name: str, commit_message: str, temp_dir: str) -> bool:
        """
        Apply patch directly using git commands
        
        Args:
            patch_file_path: Path to the patch file
            patched_files: List of files affected by the patch
            branch_name: Branch to commit to
            commit_message: Commit message
            temp_dir: Temporary directory to work in
            
        Returns:
            Success status
        """
        logger.info(f"Applying patch directly using git commands")
        
        try:
            # Clone the repository
            repo_url = self.repo_url
            if not repo_url:
                repo_url = f"https://github.com/{os.environ.get('GITHUB_REPO_OWNER', 'example')}/{os.environ.get('GITHUB_REPO_NAME', 'repo')}.git"
            
            # Add token to URL if available
            if self.github_token:
                repo_parts = repo_url.split("://")
                if len(repo_parts) == 2:
                    repo_url = f"{repo_parts[0]}://{self.github_token}@{repo_parts[1]}"
            
            logger.info(f"Cloning repository to {temp_dir}")
            subprocess.run(
                ["git", "clone", "--quiet", repo_url, temp_dir],
                check=True, 
                capture_output=True
            )
            
            # Checkout the branch
            logger.info(f"Checking out branch {branch_name}")
            subprocess.run(
                ["git", "checkout", branch_name],
                check=True, 
                capture_output=True,
                cwd=temp_dir
            )
            
            # First check if the patch can be applied cleanly
            logger.info("Checking if patch can be applied cleanly")
            try:
                subprocess.run(
                    ["git", "apply", "--check", patch_file_path],
                    check=True, 
                    capture_output=True,
                    cwd=temp_dir
                )
                logger.info("Patch can be applied cleanly")
                
                # Apply the patch
                logger.info("Applying patch")
                subprocess.run(
                    ["git", "apply", patch_file_path],
                    check=True, 
                    capture_output=True,
                    cwd=temp_dir
                )
                logger.info("Patch applied successfully")
                
                # Stage the changed files
                logger.info(f"Staging {len(patched_files)} changed files")
                for file_path in patched_files:
                    subprocess.run(
                        ["git", "add", file_path],
                        check=True, 
                        capture_output=True,
                        cwd=temp_dir
                    )
                    logger.info(f"Staged file: {file_path}")
                
                # Verify changes were applied
                status_output = subprocess.run(
                    ["git", "status", "--porcelain"],
                    check=True, 
                    capture_output=True,
                    text=True,
                    cwd=temp_dir
                ).stdout.strip()
                
                if not status_output:
                    logger.error("No changes detected after applying patch")
                    return False
                
                logger.info(f"Git status shows changes: {status_output}")
                
                # Commit changes
                logger.info(f"Committing changes with message: {commit_message}")
                subprocess.run(
                    ["git", "commit", "-m", commit_message],
                    check=True, 
                    capture_output=True,
                    cwd=temp_dir
                )
                
                # Push changes
                logger.info(f"Pushing changes to branch {branch_name}")
                subprocess.run(
                    ["git", "push", "origin", branch_name],
                    check=True, 
                    capture_output=True,
                    cwd=temp_dir
                )
                logger.info("Changes pushed successfully")
                
                return True
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Patch cannot be applied cleanly: {e.stdout if hasattr(e, 'stdout') else ''} {e.stderr if hasattr(e, 'stderr') else ''}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying patch directly: {str(e)}")
            return False
    
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
                try:
                    check_cmd = ["git", "apply", "--check", patch_file_path]
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
                        
                        # Calculate checksum and show preview of changed file
                        file_path_full = os.path.join(temp_dir, file_path)
                        if os.path.exists(file_path_full):
                            with open(file_path_full, 'rb') as f:
                                file_content = f.read()
                                checksum = hashlib.md5(file_content).hexdigest()
                                logger.info(f"File {file_path} checksum: {checksum}")
                                logger.debug(f"File preview: {file_content[:200].decode('utf-8', errors='replace')}...")
                    
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
                    
                    # Create PR using GitHub API
                    repo_owner = os.environ.get("GITHUB_REPO_OWNER", "example")
                    repo_name = os.environ.get("GITHUB_REPO_NAME", "repo")
                    
                    # Only create a PR if not in test mode
                    if not self.test_mode:
                        # Use GitHub API to create PR if token is available
                        if self.github_token:
                            try:
                                pr_data = self._create_pr_via_api(
                                    repo_owner=repo_owner, 
                                    repo_name=repo_name,
                                    title=f"Fix for {ticket_id}",
                                    body=f"This PR fixes the issue described in {ticket_id}",
                                    head=branch_name,
                                    base=os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
                                )
                                
                                if pr_data and "html_url" in pr_data and "number" in pr_data:
                                    pr_url = pr_data["html_url"]
                                    pr_number = pr_data["number"]
                                    logger.info(f"Created PR #{pr_number}: {pr_url}")
                                    
                                    result["pr_url"] = pr_url
                                    result["pr_number"] = pr_number
                                    result["pr_created"] = True
                                    
                                    return result
                            except Exception as e:
                                logger.error(f"Failed to create PR via API: {str(e)}")
                    
                    # Fallback: Generate a link that would work once pushed
                    # This isn't a real PR, but at least the URL will be correct when user creates PR manually
                    pr_url = f"https://github.com/{repo_owner}/{repo_name}/compare/{branch_name}?expand=1"
                    pr_number = None  # No PR number since it's not created yet
                    
                    logger.info(f"No PR was created, but code is pushed to branch. Compare URL: {pr_url}")
                    result["pr_url"] = pr_url
                    result["pr_number"] = pr_number
                    result["pr_created"] = False
                    
                    return result
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"Patch cannot be applied cleanly: {e.stdout if hasattr(e, 'stdout') else ''} {e.stderr if hasattr(e, 'stderr') else ''}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error applying patch using git: {str(e)}")
            
        return result

    def _create_pr_via_api(self, repo_owner: str, repo_name: str, title: str, body: str, head: str, base: str) -> Dict[str, Any]:
        """
        Create a PR using GitHub API
        
        Args:
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            
        Returns:
            Dictionary with PR data including URL and number
        """
        if not self.github_token:
            logger.error("Cannot create PR: GitHub token not available")
            return {}
            
        import requests
        
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.github_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        
        logger.info(f"Creating PR via GitHub API: {head} -> {base}")
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 201:
            pr_data = response.json()
            logger.info(f"PR created successfully: {pr_data['html_url']}")
            return pr_data
        elif response.status_code == 422 and "A pull request already exists" in response.text:
            logger.info("PR already exists, looking up the existing PR")
            
            # Try to find the existing PR
            prs_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
            params = {
                "head": f"{repo_owner}:{head}",
                "base": base,
                "state": "open"
            }
            
            response = requests.get(prs_url, headers=headers, params=params)
            
            if response.status_code == 200 and response.json():
                pr_data = response.json()[0]
                logger.info(f"Found existing PR: {pr_data['html_url']}")
                return pr_data
                
            logger.error(f"Could not find existing PR")
            return {}
        else:
            logger.error(f"Failed to create PR: {response.status_code} - {response.text}")
            return {}
    
    # ... keep existing code (_update_jira_early_escalation, _update_jira_progress, and _update_jira_final methods)
