
import os
import logging
import json
from typing import Dict, Any, Optional, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator_agent")

class CommunicatorAgent:
    """
    Agent responsible for communicating with external systems like JIRA and GitHub.
    Updates JIRA tickets with comments and progress, and creates PRs in GitHub.
    """
    
    def __init__(self, confidence_threshold: int = 70):
        """
        Initialize the communicator agent
        
        Args:
            confidence_threshold: Threshold for confidence score to consider a patch high-confidence
        """
        self.status = "idle"
        self.name = "Communicator Agent"
        self.confidence_threshold = confidence_threshold
        
        # Check if we're configured to use only the default branch
        self.use_default_branch_only = os.environ.get("GITHUB_USE_DEFAULT_BRANCH_ONLY", "False").lower() == "true"
        self.default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
        
    def process(self, communication_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute communication tasks based on the results of previous agents
        
        Args:
            communication_task: Dictionary with task details
                
        Returns:
            Dictionary with results of the communication tasks
        """
        ticket_id = communication_task.get("ticket_id", "unknown")
        logger.info(f"Communication tasks for ticket {ticket_id}")
        
        # Extract data from communication task
        update_type = communication_task.get("update_type", "final")
        patch_data = communication_task.get("patch_data", {})
        test_results = communication_task.get("test_results", {})
        task_plan = communication_task.get("task_plan", {})
        confidence_score = communication_task.get("confidence_score", 0)
        
        # Get attempt number if available
        attempt = communication_task.get("attempt", 1)
        max_retries = communication_task.get("max_retries", 4)
        
        result = {
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
        }
        
        try:
            if update_type == "progress":
                # Handle progress update
                result = self._handle_progress_update(
                    ticket_id,
                    attempt,
                    max_retries,
                    patch_data,
                    test_results,
                    communication_task.get("success", False),
                    communication_task.get("failure_summary", ""),
                    confidence_score
                )
            elif update_type == "early_escalation":
                # Handle early escalation
                result = self._handle_early_escalation(
                    ticket_id,
                    attempt,
                    max_retries,
                    patch_data,
                    communication_task.get("escalation_reason", "Unknown reason"),
                    confidence_score
                )
            else:
                # Handle final update (success or max retries)
                tests_passed = communication_task.get("success", False)
                if tests_passed:
                    # Validate conditions for PR creation and setting to Done:
                    # 1. Tests passed
                    # 2. Confidence score > threshold
                    if confidence_score >= self.confidence_threshold:
                        # All conditions met - create PR and update JIRA
                        result = self._handle_successful_fix(
                            ticket_id, patch_data, test_results, task_plan, attempt, confidence_score
                        )
                    else:
                        # Tests passed but confidence too low
                        logger.warning(f"Tests passed but confidence score too low: {confidence_score}% < {self.confidence_threshold}%")
                        result = self._handle_partial_success(
                            ticket_id, patch_data, test_results, task_plan, attempt, confidence_score,
                            "Confidence score below threshold"
                        )
                else:
                    # Tests failed - handle based on retry status
                    result = self._handle_failed_fix(
                        ticket_id, patch_data, test_results, task_plan, attempt, max_retries
                    )
                
            self.status = "success"
            logger.info(f"Communication for ticket {ticket_id} complete with result: {json.dumps(result)}")
            return result
            
        except Exception as e:
            logger.error(f"Communication tasks failed: {str(e)}")
            self.status = "failed"
            
            result["error"] = str(e)
            return result

    def _handle_progress_update(
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
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
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
        
        # Post the comment to JIRA (mock for now)
        logger.info(f"Would add JIRA comment: {comment}")
        result["jira_updated"] = True
        result["comments_added"].append(comment)
        
        # Update ticket status based on result
        if success:
            # Update to In Review only if tests passed and we're not done yet
            logger.info(f"Would update JIRA ticket {ticket_id} to status: In Review")
            result["ticket_status"] = "In Review"
        else:
            status = "In Progress" if attempt < max_retries else "Needs Review"
            logger.info(f"Would update JIRA ticket {ticket_id} to status: {status}")
            result["ticket_status"] = status
            
        return result
    
    def _handle_early_escalation(
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
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
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
        
        # Post the comment to JIRA (mock for now)
        logger.info(f"Would add JIRA comment: {comment}")
        logger.info(f"Would update JIRA ticket {ticket_id} to status: Needs Review")
        
        result["jira_updated"] = True
        result["comments_added"].append(comment)
        result["ticket_status"] = "Needs Review"
            
        return result
    
    def _handle_partial_success(
        self,
        ticket_id: str,
        patch_data: Dict[str, Any],
        test_results: Dict[str, Any],
        task_plan: Dict[str, Any],
        attempt: int,
        confidence_score: int,
        reason: str
    ) -> Dict[str, Any]:
        """Handle partial success - tests passed but other conditions not met"""
        logger.info(f"Handling partial success for ticket {ticket_id}: {reason}")
        
        result = {
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
        }
        
        # Build comment
        comment = (
            f"✅ Fix implemented with tests passing, but additional conditions not met.\n\n"
            f"Reason: {reason}\n"
        )
        
        if "confidence" in reason.lower():
            comment += f"Confidence score: {confidence_score}% (below threshold of {self.confidence_threshold}%)\n"
            
        comment += (
            f"\nThe code fix has been applied locally and all tests pass, but the ticket cannot be "
            f"automatically marked as Done. Please review the changes manually."
        )
        
        # Post the comment to JIRA (mock for now)
        logger.info(f"Would add JIRA comment: {comment}")
        logger.info(f"Would update JIRA ticket {ticket_id} to status: In Review")
        
        result["jira_updated"] = True
        result["comments_added"].append(comment)
        result["ticket_status"] = "In Review"
            
        return result
            
    def _handle_successful_fix(
        self, 
        ticket_id: str, 
        patch_data: Dict[str, Any], 
        test_results: Dict[str, Any],
        task_plan: Dict[str, Any],
        attempt: int,
        confidence_score: int
    ) -> Dict[str, Any]:
        """Handle successful fix by creating PR and updating JIRA"""
        logger.info(f"Handling successful fix for ticket {ticket_id}")
        
        result = {
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
        }
        
        # Determine which branch to use
        branch_name = self.default_branch if self.use_default_branch_only else f"bugfix/{ticket_id.lower()}"
        logger.info(f"Using branch {branch_name} for fix")
        
        # Only create a branch if we're not using the default branch only mode
        branch_created = True
        if not self.use_default_branch_only:
            # Mock branch creation for now
            logger.info(f"Would create branch: {branch_name}")
            branch_created = True
        
        if not branch_created:
            logger.error(f"Failed to create branch {branch_name}")
            
            # Update result for failed branch creation
            comment = (
                f"✅ A fix was generated but could not be committed to GitHub.\n\n"
                f"Fix attempt {attempt} was successful, but there was an issue creating the branch."
            )
            
            logger.info(f"Would add JIRA comment: {comment}")
            result["comments_added"].append(comment)
            
            return result
            
        # 2. Commit the changes
        commit_message = patch_data.get("commit_message", f"Fix bug {ticket_id}")
        if not commit_message.startswith(f"Fix {ticket_id}"):
            commit_message = f"Fix {ticket_id}: {commit_message}"
            
        patched_files = patch_data.get("patched_files", [])
        patch_content = patch_data.get("patch_content", "")
        
        # Mock commit for now
        logger.info(f"Would commit changes with message: {commit_message}")
        logger.info(f"Would apply patch to {len(patched_files)} files")
        commit_success = True
        
        if not commit_success:
            logger.error("Failed to commit changes")
            
            # Update result for failed commit
            comment = (
                f"✅ A fix was generated but could not be committed to GitHub.\n\n"
                f"Fix attempt {attempt} was successful, but there was an issue committing the changes."
            )
            
            logger.info(f"Would add JIRA comment: {comment}")
            result["comments_added"].append(comment)
            
            return result
        
        # 3. Create a PR - only if not using default branch only mode
        pr_url = None
        pr_created = False
        
        if not self.use_default_branch_only:
            logger.info("Creating pull request")
            
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
            
            # Mock PR creation for now
            logger.info(f"Would create PR with title: {pr_title}")
            logger.info(f"PR body: {pr_body}")
            pr_url = f"https://github.com/example/repo/pull/123"  # Mock URL
            pr_created = True
            
            if not pr_created:
                logger.error("Failed to create pull request")
                
                # Update result for failed PR creation
                comment = (
                    f"✅ A fix was generated and committed to branch `{branch_name}`, "
                    f"but there was an issue creating the pull request."
                )
                
                logger.info(f"Would add JIRA comment: {comment}")
                logger.info(f"Would update JIRA ticket {ticket_id} to status: In Review")
                
                result["jira_updated"] = True
                result["comments_added"].append(comment)
                result["ticket_status"] = "In Review"
                
                return result
        
        # 4. Validate all conditions for marking as Done:
        # 1. PR created successfully (or default branch mode)
        # 2. Confidence score > threshold (already checked by caller)
        # 3. Tests passed (already checked by caller)
        
        final_ticket_status = "Done"
        
        if not pr_created and not self.use_default_branch_only:
            final_ticket_status = "In Review"
            logger.warning("Cannot set ticket to Done - PR creation failed")
        
        # Update JIRA with success
        logger.info(f"All conditions met, updating JIRA ticket {ticket_id} to status: {final_ticket_status}")
        
        comment = (
            f"✅ Fix implemented successfully!\n\n"
            f"All tests are passing.\n"
        )
        
        if pr_url:
            comment += f"Pull Request: {pr_url}\n\n"
        else:
            comment += f"Changes were committed directly to the {self.default_branch} branch.\n\n"
            
        comment += f"Fix generated on attempt {attempt} with confidence score {confidence_score}%."
        
        logger.info(f"Would add JIRA comment: {comment}")
        
        result["jira_updated"] = True
        result["pr_created"] = pr_created
        result["pr_url"] = pr_url
        result["comments_added"].append(comment)
        result["ticket_status"] = final_ticket_status
        
        return result
        
    def _handle_failed_fix(
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
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
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
            
            logger.info(f"Would add JIRA comment: {comment}")
            logger.info(f"Would update JIRA ticket {ticket_id} to status: Needs Review")
            
            result["jira_updated"] = True
            result["comments_added"].append(comment)
            result["ticket_status"] = "Needs Review"
            
        else:
            # More retries available - update with current status
            logger.info(f"Attempt {attempt}/{max_retries} failed, more retries available")
            
            comment = (
                f"❌ Fix attempt {attempt}/{max_retries} failed.\n\n"
                f"Error: {test_results.get('error_message', 'Unknown error')}\n\n"
                f"Retrying with a different approach..."
            )
            
            logger.info(f"Would add JIRA comment: {comment}")
            logger.info(f"Would update JIRA ticket {ticket_id} to status: In Progress")
            
            result["jira_updated"] = True
            result["comments_added"].append(comment)
            result["ticket_status"] = "In Progress"
            
        return result
    
    def report(self) -> str:
        """
        Generate a report of the agent's activity
        
        Returns:
            String with report
        """
        return f"Communicator Agent Status: {self.status}"
