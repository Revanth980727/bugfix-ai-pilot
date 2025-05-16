
import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator-agent")

class CommunicatorAgent:
    """
    Agent responsible for communicating with external systems like JIRA and GitHub.
    Updates JIRA tickets with comments and progress, and creates PRs in GitHub.
    """
    
    def __init__(self):
        """Initialize the communicator agent"""
        try:
            # Try to import JiraClient and GitHubClient
            from .utils.jira_client import JiraClient
            from .utils.github_client import GitHubClient
            
            self.jira_client = JiraClient()
            self.github_client = GitHubClient()
            self.mocked_github = False
            
            # Log successful initialization
            logger.info("Successfully initialized JIRA and GitHub clients")
            
            # Check if we're configured to use only the default branch
            self.use_default_branch_only = os.environ.get("GITHUB_USE_DEFAULT_BRANCH_ONLY", "False").lower() == "true"
            self.default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
            self.test_mode = os.environ.get("TEST_MODE", "False").lower() == "true"
            
            if self.test_mode:
                logger.warning("Running in TEST_MODE - real GitHub/JIRA interactions may be mocked")
                
        except ImportError as e:
            logger.warning(f"Error importing API clients, attempting fallback: {str(e)}")
            self.init_fallback()
            
    def init_fallback(self):
        """Initialize fallback mock clients if real ones can't be imported"""
        try:
            # Create mock clients if the real ones couldn't be imported
            from unittest.mock import MagicMock, AsyncMock
            
            self.jira_client = MagicMock()
            self.jira_client.add_comment = AsyncMock(return_value=True)
            self.jira_client.update_ticket = AsyncMock(return_value=True)
            
            self.github_client = MagicMock()
            self.github_client.create_branch = MagicMock(return_value=True)
            self.github_client.commit_patch = MagicMock(return_value=True)
            self.github_client.create_pull_request = MagicMock(return_value=(None, None))
            
            self.mocked_github = True
            logger.warning("GitHub service could not be imported - will mock GitHub interactions")
            
            # Default settings
            self.use_default_branch_only = False
            self.default_branch = "main"
            self.test_mode = True
            
        except Exception as e:
            logger.error(f"Critical error initializing fallback clients: {str(e)}")
            raise
            
    async def run(self, communication_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute communication tasks based on the results of previous agents
        
        Args:
            communication_task: Dictionary with task details:
                {
                    "ticket_id": "PROJ-123",
                    "update_type": "progress" | "early_escalation" | "final",
                    "patch_data": { patch details from DeveloperAgent },
                    "test_results": { test results from QAAgent },
                    "task_plan": { task plan from PlannerAgent },
                    "attempt": 1,
                    "max_retries": 4,
                    "confidence_score": 75,
                    "escalation_reason": "reason" (only for early_escalation),
                    ...
                }
                
        Returns:
            Dictionary with results of the communication tasks
        """
        ticket_id = communication_task.get("ticket_id", "unknown")
        logger.info(f"Communication tasks for ticket {ticket_id}")
        
        # Extract data from communication task
        update_type = communication_task.get("update_type", "final")
        
        # Extract patch data carefully - multiple possible formats
        patch_data = self._extract_patch_data(communication_task)
        
        # Log actual patch data details for debugging
        self._log_patch_data_details(patch_data)
        
        test_results = communication_task.get("test_results", {})
        task_plan = communication_task.get("task_plan", {})
        confidence_score = communication_task.get("confidence_score", 75)
        
        # Get attempt number if available
        attempt = communication_task.get("attempt", communication_task.get("retry_count", 1))
        max_retries = communication_task.get("max_retries", 4)
        
        result = {
            "ticket_id": ticket_id,
            "jira_updated": False,
            "github_updated": False,
            "github_pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown",
            "test_passed": communication_task.get("test_passed", False)
        }
        
        try:
            if update_type == "progress":
                # Handle progress update
                result = await self._handle_progress_update(
                    ticket_id,
                    attempt,
                    max_retries,
                    patch_data,
                    test_results,
                    communication_task.get("success", communication_task.get("test_passed", False)),
                    communication_task.get("failure_summary", ""),
                    confidence_score
                )
            elif update_type == "early_escalation":
                # Handle early escalation
                result = await self._handle_early_escalation(
                    ticket_id,
                    attempt,
                    max_retries,
                    patch_data,
                    communication_task.get("escalation_reason", "Unknown reason"),
                    confidence_score
                )
            else:
                # Handle final update (success or max retries)
                tests_passed = communication_task.get("success", communication_task.get("test_passed", False))
                if tests_passed:
                    # Tests passed - update JIRA and create PR
                    result = await self._handle_successful_fix(
                        ticket_id, patch_data, test_results, task_plan, attempt
                    )
                else:
                    # Tests failed - handle based on retry status
                    result = await self._handle_failed_fix(
                        ticket_id, patch_data, test_results, task_plan, attempt, max_retries
                    )
                
            logger.info(f"Communication for ticket {ticket_id} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Communication tasks failed: {str(e)}")
            
            result["error"] = str(e)
            return result
    
    def _extract_patch_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract patch data from various possible formats in the task data.
        
        Handles:
        1. Direct patch_content and patched_files
        2. Patches list with file_path and diff
        3. Nested developer_result containing any of the above
        """
        patch_data = {}
        
        # Check for "patches" format (list of dicts with file_path and diff)
        if "patches" in task_data and isinstance(task_data["patches"], list):
            patches = task_data["patches"]
            if patches:
                patch_data["patches"] = patches
                # Extract file paths from patches for convenience
                patch_data["patched_files"] = [p.get("file_path") for p in patches if p.get("file_path")]
                
                # Generate combined patch content
                combined_patch = ""
                for patch in patches:
                    file_path = patch.get("file_path")
                    diff = patch.get("diff")
                    if file_path and diff:
                        combined_patch += f"--- a/{file_path}\n+++ b/{file_path}\n{diff}\n"
                
                if combined_patch:
                    patch_data["patch_content"] = combined_patch
        
        # Check for direct patch_content and patched_files
        if "patch_content" in task_data and task_data["patch_content"]:
            patch_data["patch_content"] = task_data["patch_content"]
        
        if "patched_files" in task_data and task_data["patched_files"]:
            patch_data["patched_files"] = task_data["patched_files"]
        
        # Look for nested developer_result
        developer_result = task_data.get("developer_result", {})
        if developer_result and isinstance(developer_result, dict):
            # Check for patches in developer_result
            if "patches" in developer_result and isinstance(developer_result["patches"], list):
                patches = developer_result["patches"]
                if patches:
                    patch_data["patches"] = patches
                    # Extract file paths from patches
                    patch_data["patched_files"] = [p.get("file_path") for p in patches if p.get("file_path")]
                    
                    # Generate combined patch content if not already present
                    if "patch_content" not in patch_data:
                        combined_patch = ""
                        for patch in patches:
                            file_path = patch.get("file_path")
                            diff = patch.get("diff")
                            if file_path and diff:
                                combined_patch += f"--- a/{file_path}\n+++ b/{file_path}\n{diff}\n"
                        
                        if combined_patch:
                            patch_data["patch_content"] = combined_patch
            
            # Check for direct patch_content and patched_files in developer_result
            if "patch_content" in developer_result and developer_result["patch_content"]:
                patch_data["patch_content"] = developer_result["patch_content"]
            
            if "patched_files" in developer_result and developer_result["patched_files"]:
                patch_data["patched_files"] = developer_result["patched_files"]
            
            # Also copy commit message if present
            if "commit_message" in developer_result:
                patch_data["commit_message"] = developer_result["commit_message"]
        
        # Copy commit message from top level if present and not already set
        if "commit_message" in task_data and "commit_message" not in patch_data:
            patch_data["commit_message"] = task_data["commit_message"]
        
        return patch_data
    
    def _log_patch_data_details(self, patch_data: Dict[str, Any]) -> None:
        """Log detailed patch data information for debugging"""
        has_patches = "patches" in patch_data and isinstance(patch_data["patches"], list) and len(patch_data["patches"]) > 0
        has_patch_content = "patch_content" in patch_data and patch_data["patch_content"] and len(patch_data["patch_content"]) > 0
        patched_files_count = len(patch_data.get("patched_files", [])) if "patched_files" in patch_data else 0
        
        logger.info(f"Patch data formats - patches list: {has_patches}, " +
                    f"patch_content: {has_patch_content}, " +
                    f"patched_files: {patched_files_count}")
        
        if has_patches:
            patch_files = [p.get("file_path") for p in patch_data["patches"] if p.get("file_path")]
            logger.info(f"Patches format contains {len(patch_files)} files: {', '.join(patch_files)}")
            
        if has_patch_content:
            content_length = len(patch_data["patch_content"])
            content_preview = patch_data["patch_content"][:100] + "..." if content_length > 100 else patch_data["patch_content"]
            logger.info(f"Patch content present ({content_length} chars): {content_preview}")
            
        if "patched_files" in patch_data and patch_data["patched_files"]:
            logger.info(f"Patched files: {', '.join(patch_data['patched_files'])}")
            
        if not (has_patches or has_patch_content or patched_files_count > 0):
            logger.warning("No valid patch data found in any format")
            
    async def _handle_progress_update(
        self,
        ticket_id: str,
        attempt: int,
        max_retries: int,
        patch_data: Dict[str, Any],
        test_results: Optional[Dict[str, Any]],
        success: bool,
        failure_summary: str,
        confidence_score: int
    ) -> Dict[str, Any]:
        """Handle a progress update - post detailed JIRA comment"""
        logger.info(f"Posting progress update for ticket {ticket_id}, attempt {attempt}/{max_retries}")
        
        result = {
            "ticket_id": ticket_id,
            "jira_updated": False,
            "github_updated": False,
            "github_pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown",
            "test_passed": success
        }
        
        # Build a structured JIRA comment
        comment = f"🔁 Attempt {attempt}/{max_retries}\n"
        comment += f"🛠️ Developer Agent submitted a patch (confidence: {confidence_score}%)\n"
        
        # Add modified files if available
        patched_files = patch_data.get("patched_files", [])
        if patched_files:
            comment += "📝 Modified files:\n"
            for file_path in patched_files[:5]:  # Limit to first 5 files
                comment += f"- `{file_path}`\n"
            if len(patched_files) > 5:
                comment += f"- ... and {len(patched_files) - 5} more files\n"
        
        # Add QA results if available
        if test_results is not None:
            if success:
                comment += "✅ QA Agent Result: PASS\n"
                comment += f"⏱️ Tests executed in {test_results.get('execution_time', 0):.2f} seconds\n"
            else:
                comment += "❌ QA Agent Result: FAIL\n"
                if failure_summary:
                    comment += f"📋 Error Summary:\n{failure_summary}\n"
        else:
            comment += "⚠️ No QA results available\n"
        
        # Post the comment to JIRA
        try:
            await self.jira_client.add_comment(ticket_id, comment)
            result["jira_updated"] = True
            result["comments_added"].append(comment)
        except Exception as e:
            logger.error(f"Failed to add JIRA comment: {str(e)}")
        
        # Update ticket status based on result
        try:
            if success:
                status = "In Review"
                await self.jira_client.update_ticket(ticket_id, status, "Fix implemented, awaiting PR creation")
                result["ticket_status"] = status
            else:
                status = "In Progress" if attempt < max_retries else "Needs Review"
                await self.jira_client.update_ticket(ticket_id, status, "")
                result["ticket_status"] = status
        except Exception as e:
            logger.error(f"Failed to update ticket status: {str(e)}")
            
        return result
    
    async def _handle_early_escalation(
        self,
        ticket_id: str,
        attempt: int,
        max_retries: int,
        patch_data: Dict[str, Any],
        escalation_reason: str,
        confidence_score: int
    ) -> Dict[str, Any]:
        """Handle early escalation - notify in JIRA that we're escalating early"""
        logger.info(f"Handling early escalation for ticket {ticket_id} at attempt {attempt}/{max_retries}")
        
        result = {
            "ticket_id": ticket_id,
            "jira_updated": False,
            "github_updated": False,
            "github_pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown",
            "test_passed": False
        }
        
        # Build early escalation comment
        comment = f"⚠️ Early Escalation after attempt {attempt}/{max_retries}\n\n"
        comment += f"Reason for escalation: {escalation_reason}\n\n"
        
        if "confidence" in escalation_reason.lower():
            comment += f"Patch confidence score: {confidence_score}% (below threshold)\n"
            comment += "The AI has determined that it cannot produce a high-confidence fix for this issue.\n"
        elif "pattern" in escalation_reason.lower():
            comment += "Multiple attempts resulted in the same failure pattern.\n"
            comment += "The AI is unable to make progress after repeated attempts with similar errors.\n"
        
        comment += "\nThis ticket requires human attention."
        
        # Post the comment to JIRA
        try:
            await self.jira_client.add_comment(ticket_id, comment)
            await self.jira_client.update_ticket(ticket_id, "Needs Review", "Escalated by Bug Fix AI")
            
            result["jira_updated"] = True
            result["comments_added"].append(comment)
            result["ticket_status"] = "Needs Review"
        except Exception as e:
            logger.error(f"Failed to handle early escalation in JIRA: {str(e)}")
            
        return result
            
    async def _handle_successful_fix(
        self, 
        ticket_id: str, 
        patch_data: Dict[str, Any], 
        test_results: Dict[str, Any],
        task_plan: Dict[str, Any],
        attempt: int
    ) -> Dict[str, Any]:
        """Handle successful fix by creating PR and updating JIRA"""
        logger.info(f"Handling successful fix for ticket {ticket_id}")
        
        result = {
            "ticket_id": ticket_id,
            "jira_updated": False,
            "github_updated": False,
            "github_pr_url": None,
            "pr_created": False,
            "comments_added": [],
            "ticket_status": "unknown",
            "test_passed": True
        }
        
        # Determine which branch to use
        branch_name = self.default_branch if self.use_default_branch_only else f"bugfix/{ticket_id.lower()}"
        logger.info(f"Using branch {branch_name} for fix")
        
        # Check if we have valid patch data
        has_valid_patches = self._validate_patch_data(patch_data, result)
        if not has_valid_patches:
            logger.warning(f"No valid patches to apply for ticket {ticket_id}")
            return result
        
        # Only create a branch if we're not using the default branch only mode
        if not self.use_default_branch_only:
            try:
                branch_created = self.github_client.create_branch(branch_name)
                if not branch_created:
                    logger.error(f"Failed to create branch {branch_name}")
                    return result
            except Exception as e:
                logger.error(f"Exception creating branch: {str(e)}")
                return result
        
        # 2. Commit the changes
        commit_message = patch_data.get("commit_message", f"Fix bug {ticket_id}")
        if not commit_message.startswith(f"Fix {ticket_id}"):
            commit_message = f"Fix {ticket_id}: {commit_message}"
            
        patched_files = patch_data.get("patched_files", [])
        patch_content = patch_data.get("patch_content", "")
        
        # Apply the patch via GitHub API
        try:
            commit_success = self.github_client.commit_patch(
                branch_name=branch_name,
                patch_content=patch_content,
                commit_message=commit_message,
                patch_file_paths=patched_files
            )
            
            if not commit_success:
                logger.error("Failed to commit changes")
                
                # Update JIRA with error
                comment = (
                    f"✅ A fix was generated but could not be committed to GitHub.\n\n"
                    f"Fix attempt {attempt} was successful, but there was an issue committing the changes."
                )
                await self.jira_client.add_comment(ticket_id, comment)
                result["comments_added"].append(comment)
                
                return result
                
            result["github_updated"] = True
        except Exception as e:
            logger.error(f"Exception committing patch: {str(e)}")
            return result
        
        # 3. Create a PR - only if not using default branch only mode
        logger.info("Creating pull request")
        
        pr_url = None
        if not self.use_default_branch_only:
            pr_title = f"Fix {ticket_id}"
            
            # Create a detailed PR description
            fix_approach = task_plan.get("approach", "")
            root_cause = task_plan.get("root_cause", "")
            
            pr_body = (
                f"## Fix for {ticket_id}\n\n"
                f"### Root Cause\n{root_cause}\n\n"
                f"### Fix Approach\n{fix_approach}\n\n"
                f"### Changes Made\n"
            )
            
            for file_path in patched_files:
                pr_body += f"- Modified `{file_path}`\n"
                
            pr_body += f"\n### Test Results\n"
            pr_body += f"✅ All tests passed in {test_results.get('execution_time', 0):.2f} seconds\n"
            
            if "test_coverage" in test_results:
                pr_body += f"📊 Test coverage: {test_results['test_coverage']}%\n"
                
            pr_body += f"\n*This PR was created automatically by BugFix AI*"
            
            # Create the PR
            try:
                pr_result = self.github_client.create_pull_request(
                    title=pr_title,
                    body=pr_body,
                    head_branch=branch_name,
                    base_branch=None  # Use default
                )
                
                # Handle different return types from different implementations
                if isinstance(pr_result, tuple) and len(pr_result) >= 1:
                    pr_url = pr_result[0]
                elif isinstance(pr_result, dict) and "url" in pr_result:
                    pr_url = pr_result["url"]
                else:
                    pr_url = str(pr_result) if pr_result else None
                
                # Validate PR URL - don't allow placeholder URLs in non-test mode
                if (not self.test_mode and pr_url and 
                    ("org/repo" in pr_url or "example.com" in pr_url or ticket_id in pr_url)):
                    logger.warning(f"Generated placeholder PR URL in non-test mode: {pr_url}")
                    pr_url = None
                
                if not pr_url:
                    logger.error("Failed to create pull request - no URL returned")
                    
                    # Update JIRA with error
                    comment = (
                        f"✅ A fix was generated and committed to branch `{branch_name}`, "
                        f"but there was an issue creating the pull request."
                    )
                    await self.jira_client.add_comment(ticket_id, comment)
                    result["comments_added"].append(comment)
                    
                    return result
                    
                result["pr_created"] = True
                result["github_pr_url"] = pr_url
            except Exception as e:
                logger.error(f"Exception creating PR: {str(e)}")
                return result
        
        # 4. Update JIRA with success
        logger.info(f"Updating JIRA ticket {ticket_id}")
        
        comment = (
            f"✅ Fix implemented successfully!\n\n"
            f"All tests are passing.\n"
        )
        
        if pr_url:
            comment += f"Pull Request: {pr_url}\n\n"
        else:
            comment += f"Changes were committed directly to the {self.default_branch} branch.\n\n"
            
        comment += f"Fix generated on attempt {attempt}."
        
        try:
            await self.jira_client.add_comment(ticket_id, comment)
            await self.jira_client.update_ticket(ticket_id, "In Review", comment)
            
            result["jira_updated"] = True
            result["comments_added"].append(comment)
            result["ticket_status"] = "In Review"
        except Exception as e:
            logger.error(f"Exception updating JIRA: {str(e)}")
        
        return result
        
    async def _handle_failed_fix(
        self, 
        ticket_id: str, 
        patch_data: Dict[str, Any], 
        test_results: Dict[str, Any],
        task_plan: Dict[str, Any],
        attempt: int,
        max_retries: int
    ) -> Dict[str, Any]:
        """Handle failed fix based on retry status"""
        logger.info(f"Handling failed fix for ticket {ticket_id}, attempt {attempt}/{max_retries}")
        
        result = {
            "ticket_id": ticket_id,
            "jira_updated": False,
            "github_updated": False,
            "github_pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown",
            "test_passed": False
        }
        
        # Check if we've reached max retries
        if attempt >= max_retries:
            # Max retries reached - escalate
            logger.info(f"Max retries ({max_retries}) reached, escalating")
            
            comment = (
                f"⚠️ Could not fix this ticket automatically after {attempt} attempts. "
                f"Escalating to human reviewer.\n\n"
                f"Latest error: {test_results.get('error_message', 'Unknown error')}"
            )
            
            try:
                await self.jira_client.add_comment(ticket_id, comment)
                await self.jira_client.update_ticket(ticket_id, "Needs Review", comment)
                
                result["jira_updated"] = True
                result["comments_added"].append(comment)
                result["ticket_status"] = "Needs Review"
            except Exception as e:
                logger.error(f"Exception updating JIRA for max retries: {str(e)}")
            
        else:
            # More retries available - update with current status
            logger.info(f"Attempt {attempt}/{max_retries} failed, more retries available")
            
            comment = (
                f"❌ Fix attempt {attempt}/{max_retries} failed.\n\n"
                f"Error: {test_results.get('error_message', 'Unknown error')}\n\n"
                f"Retrying with a different approach..."
            )
            
            try:
                await self.jira_client.add_comment(ticket_id, comment)
                
                result["jira_updated"] = True
                result["comments_added"].append(comment)
                result["ticket_status"] = "In Progress"
            except Exception as e:
                logger.error(f"Exception updating JIRA for retry: {str(e)}")
            
        return result
    
    def _validate_patch_data(self, patch_data: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Validate patch data to ensure it's properly formatted and contains actual changes.
        Updates the result dictionary with validation details.
        
        Returns True if patch data is valid, False otherwise.
        """
        validation_errors = []
        validation_passed = False
        
        # Check if patches list is provided
        has_patches = "patches" in patch_data and isinstance(patch_data["patches"], list) and len(patch_data["patches"]) > 0
        
        # Check if patch_content and patched_files are provided
        has_patch_content = "patch_content" in patch_data and patch_data["patch_content"] and len(patch_data["patch_content"].strip()) > 0
        has_patched_files = "patched_files" in patch_data and isinstance(patch_data["patched_files"], list) and len(patch_data["patched_files"]) > 0
        
        # Log detailed validation
        logger.info(f"Patch validation - has_patches: {has_patches}, has_patch_content: {has_patch_content}, has_patched_files: {has_patched_files}")
        
        # Check for specific validation issues
        if not has_patches and not (has_patch_content and has_patched_files):
            validation_errors.append("No valid patch data provided")
        elif has_patch_content and not has_patched_files:
            validation_errors.append("Patch content provided but no patched files list")
        elif not has_patch_content and has_patched_files:
            validation_errors.append("Patched files list provided but no patch content")
        elif has_patches:
            valid_patches = [p for p in patch_data["patches"] if p.get("file_path") and p.get("diff")]
            if len(valid_patches) == 0:
                validation_errors.append("Patches list contains no valid entries (require both file_path and diff)")
            else:
                validation_passed = True
        elif has_patch_content and has_patched_files:
            # Validate patch content format
            if not patch_data["patch_content"].startswith("--- a/") and not patch_data["patch_content"].startswith("diff --git"):
                validation_errors.append("Patch content does not appear to be in valid diff format")
            else:
                validation_passed = True
        
        # Add validation results to the result dict
        result["patch_valid"] = validation_passed
        
        if not validation_passed:
            result["rejection_reason"] = "; ".join(validation_errors)
            logger.warning(f"Patch validation failed: {result['rejection_reason']}")
        else:
            logger.info("Patch validation passed")
        
        return validation_passed
