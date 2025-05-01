
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime
import time
from .agent_base import Agent, AgentStatus
from backend.jira_service.jira_client import JiraClient
from backend.github_service.github_service import GitHubService
from backend.env import verify_github_repo_settings
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator-agent")

class CommunicatorAgent(Agent):
    def __init__(self):
        super().__init__(name="CommunicatorAgent")
        self.jira_client = JiraClient()
        self.github_service = GitHubService()
        self.max_api_retries = 3  # Maximum retries for API calls
        # Define fallback status transitions for different JIRA workflows
        self.status_fallbacks = {
            "Resolved": ["Done", "Ready for Release", "Fixed", "Closed", "In Review"]
        }
        
    async def _update_jira_ticket(self, ticket_id: str, status: str, comment: str) -> bool:
        """Update JIRA ticket with status and comment with retry logic"""
        retry_count = 0
        while retry_count < self.max_api_retries:
            try:
                # Try the requested status first
                success = await self.jira_client.update_ticket(ticket_id, status, comment)
                if success:
                    logger.info(f"Successfully updated JIRA ticket {ticket_id}")
                    return success
                else:
                    # If the requested status failed, try fallback statuses if available
                    if status in self.status_fallbacks:
                        for fallback_status in self.status_fallbacks[status]:
                            logger.info(f"Trying fallback status '{fallback_status}' for ticket {ticket_id}")
                            fallback_success = await self.jira_client.update_ticket(ticket_id, fallback_status, comment)
                            if fallback_success:
                                logger.info(f"Successfully updated JIRA ticket {ticket_id} with fallback status '{fallback_status}'")
                                return True
                    
                    logger.warning(f"Failed to update JIRA ticket {ticket_id}, retrying ({retry_count + 1}/{self.max_api_retries})")
                    retry_count += 1
                    if retry_count < self.max_api_retries:
                        # Exponential backoff
                        await asyncio.sleep(2 ** retry_count)
            except Exception as e:
                logger.error(f"Error updating JIRA ticket {ticket_id}: {str(e)}")
                retry_count += 1
                if retry_count < self.max_api_retries:
                    # Exponential backoff
                    await asyncio.sleep(2 ** retry_count)
                else:
                    logger.error(f"Max retries reached for JIRA update on ticket {ticket_id}")
                    return False
        
        logger.error(f"Failed to update JIRA ticket {ticket_id} after {self.max_api_retries} attempts")
        return False
    
    async def _get_valid_pr_url(self, ticket_id: str, github_pr_url: str = None) -> Optional[str]:
        """
        Get a valid PR URL for a ticket, either from the provided URL or by looking up the branch
        
        Args:
            ticket_id: The JIRA ticket ID
            github_pr_url: Optional PR URL already provided
            
        Returns:
            Optional[str]: Valid PR URL if found, None otherwise
        """
        # First check if we already have a valid PR URL
        if github_pr_url and isinstance(github_pr_url, str):
            # Verify this is a proper PR URL with numeric PR number
            url_match = re.search(r'/pull/(\d+)', github_pr_url)
            if url_match and url_match.group(1).isdigit():
                logger.info(f"Using provided PR URL: {github_pr_url}")
                return github_pr_url
            else:
                logger.warning(f"Provided PR URL is invalid: {github_pr_url}")
        
        # Try to find a PR for this ticket by looking up the branch
        pr_info = self.github_service.find_pr_for_ticket(ticket_id)
        if pr_info and "url" in pr_info:
            logger.info(f"Found PR URL for ticket {ticket_id}: {pr_info['url']}")
            return pr_info["url"]
            
        logger.warning(f"No valid PR URL found for ticket {ticket_id}")
        return None
            
    async def _post_github_comment(self, ticket_id: str, pr_url: str, comment: str) -> bool:
        """Post a comment on GitHub PR with retry logic"""
        retry_count = 0
        
        # First, ensure we have a valid PR URL
        if not pr_url or not isinstance(pr_url, str):
            # Try to find the PR URL based on ticket ID
            pr_url = await self._get_valid_pr_url(ticket_id)
            if not pr_url:
                logger.error(f"No valid PR URL found for ticket {ticket_id}")
                return False
        
        while retry_count < self.max_api_retries:
            try:
                # Verify GitHub settings
                github_ok, _ = verify_github_repo_settings()
                if not github_ok:
                    logger.error("GitHub settings are not properly configured")
                    return False
                
                # Extract PR number from URL
                pr_number = None
                url_match = re.search(r'/pull/(\d+)', pr_url)
                if url_match:
                    pr_number = url_match.group(1)
                else:
                    logger.error(f"Could not extract PR number from URL: {pr_url}")
                    return False
                
                # Validate that the PR number is numeric (not a ticket ID)
                if not pr_number.isdigit():
                    logger.error(f"Invalid PR number format from URL: {pr_url}, extracted: {pr_number}")
                    return False
                    
                # Post comment using GitHub service
                success = self.github_service.add_pr_comment(pr_number, comment)
                if success:
                    logger.info(f"Successfully added comment to PR {pr_url}")
                    return True
                else:
                    logger.warning(f"Failed to add comment to PR {pr_url}, retrying ({retry_count + 1}/{self.max_api_retries})")
                    retry_count += 1
                    if retry_count < self.max_api_retries:
                        # Exponential backoff
                        await asyncio.sleep(2 ** retry_count)
            except Exception as e:
                logger.error(f"Error posting GitHub comment: {str(e)}")
                retry_count += 1
                if retry_count < self.max_api_retries:
                    # Exponential backoff
                    await asyncio.sleep(2 ** retry_count)
                else:
                    logger.error(f"Max retries reached for GitHub comment on PR {pr_url}")
                    return False
        
        logger.error(f"Failed to post GitHub comment to PR {pr_url} after {self.max_api_retries} attempts")
        return False

    async def _apply_gpt_fixes_to_code(self, ticket_id: str, gpt_output: Dict[str, Any]) -> Optional[str]:
        """
        Apply GPT-suggested fixes to code and commit to GitHub
        
        Args:
            ticket_id: The JIRA ticket ID
            gpt_output: Dictionary containing GPT output
            
        Returns:
            Optional[str]: PR URL if created, None otherwise
        """
        try:
            # Create a new branch for the fix
            branch_name = f"fix/{ticket_id}"
            branch_created = self.github_service.create_fix_branch(ticket_id)
            if not branch_created:
                logger.error(f"Failed to create branch for ticket {ticket_id}")
                return None
                
            # Extract file paths and GPT response
            raw_gpt_response = gpt_output.get("raw_gpt_response", "")
            files_modified = gpt_output.get("files_modified", [])
            
            # If no specific files were identified, try to extract from the GPT response
            if not files_modified and raw_gpt_response:
                import re
                file_pattern = r'---FILE: (.*?)---'
                file_matches = re.findall(file_pattern, raw_gpt_response, re.DOTALL)
                files_modified = [f.strip() for f in file_matches]
            
            # Apply changes to each file
            success = False
            if files_modified and raw_gpt_response:
                for file_path in files_modified:
                    # If file path starts with /path/to, it's likely a placeholder
                    if file_path.startswith("/path/to/"):
                        logger.warning(f"Skipping placeholder file path: {file_path}")
                        continue
                        
                    # Apply changes to this file
                    file_success = self.github_service.apply_file_changes_from_gpt(
                        branch_name, file_path, raw_gpt_response, ticket_id
                    )
                    success = success or file_success
                    
            # Create a pull request if changes were applied
            pr_url = None
            if success:
                pr_url = self.github_service.create_fix_pr(
                    branch_name, 
                    ticket_id, 
                    f"Fix for {ticket_id}", 
                    f"Applied GPT-suggested fixes for {ticket_id}"
                )
                
                if pr_url:
                    # Verify PR URL contains a numeric PR number
                    url_match = re.search(r'/pull/(\d+)', pr_url)
                    if not url_match:
                        logger.error(f"Created PR URL does not contain numeric PR number: {pr_url}")
                        return None
                        
                    pr_number = url_match.group(1)
                    if not pr_number.isdigit():
                        logger.error(f"Non-numeric PR number detected: {pr_number}")
                        return None
                        
                    # Add the GPT response as a comment on the PR
                    comment_success = await self._post_github_comment(
                        ticket_id,
                        pr_url, 
                        f"# GPT-4 Analysis\n\n```\n{raw_gpt_response}\n```"
                    )
                    
                    if not comment_success:
                        logger.warning(f"Failed to add GPT analysis comment to PR {pr_url}")
                    
                    return pr_url
                    
            return None
            
        except Exception as e:
            logger.error(f"Error applying GPT fixes to code: {str(e)}")
            return None

    async def format_agent_comment(self, agent_type: str, message: str, attempt: int = None, max_attempts: int = None) -> str:
        """Format a structured comment for a specific agent type"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"[{agent_type.upper()} AGENT] - {timestamp}"
        
        if attempt is not None and max_attempts is not None:
            header += f" (Attempt {attempt}/{max_attempts})"
            
        return f"{header}\n\n{message}"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process communication tasks based on test results"""
        ticket_id = input_data.get("ticket_id")
        test_passed = input_data.get("test_passed", False)
        github_pr_url = input_data.get("github_pr_url")
        retry_count = input_data.get("retry_count", 0)
        max_retries = input_data.get("max_retries", 4)
        escalated = input_data.get("escalated", False)
        early_escalation = input_data.get("early_escalation", False)
        early_escalation_reason = input_data.get("early_escalation_reason")
        confidence_score = input_data.get("confidence_score")
        agent_type = input_data.get("agent_type", "system")
        qa_results = input_data.get("qa_results", {})
        failure_details = input_data.get("failure_details", "")
        failure_summary = input_data.get("failure_summary", "")
        
        # Get developer results which might contain GPT output
        developer_result = input_data.get("developer_result", {})
        
        if not ticket_id:
            raise ValueError("ticket_id is required")
        
        self.log(f"Processing communication for ticket {ticket_id}")
        
        jira_updates_success = True
        github_updates_success = True
        updates = []
        
        # Timestamp for updates
        timestamp = datetime.now().isoformat()
        
        # Get or find a valid PR URL based on ticket ID
        valid_pr_url = await self._get_valid_pr_url(ticket_id, github_pr_url)
        
        # If no PR URL is available but we have developer results, try to create one
        if not valid_pr_url and developer_result and not test_passed:
            self.log("No valid PR URL found, attempting to create one from developer results")
            valid_pr_url = await self._apply_gpt_fixes_to_code(ticket_id, developer_result)
        
        # Use the validated PR URL for all operations
        github_pr_url = valid_pr_url
        
        if early_escalation:
            # Handle early escalation (before max retries)
            reason = early_escalation_reason or "Automated fix determined to be low confidence"
            
            jira_comment = await self.format_agent_comment(
                "Communicator",
                f"⚠️ Early escalation after attempt {retry_count}/{max_retries}.\n"
                f"Reason: {reason}" +
                (f" (Confidence score: {confidence_score}%)" if confidence_score is not None else ""),
                retry_count,
                max_retries
            )
            
            updates.append({
                "timestamp": timestamp,
                "message": f"⚠️ Early escalation: {reason}" + 
                          (f" (Confidence score: {confidence_score}%)" if confidence_score is not None else ""),
                "type": "jira",
                "confidenceScore": confidence_score
            })
            
            # Add system message for frontend
            updates.append({
                "timestamp": timestamp,
                "message": f"Ticket escalated early: {reason}",
                "type": "system"
            })
            
            jira_updates_success = await self._update_jira_ticket(
                ticket_id,
                "Needs Review",
                jira_comment
            )
            
            if github_pr_url:
                github_comment = f"⚠️ Early escalation: {reason}"
                if confidence_score is not None:
                    github_comment += f" (Confidence score: {confidence_score}%)"
                
                github_updates_success = await self._post_github_comment(
                    ticket_id,
                    github_pr_url,
                    github_comment
                )
                
                if github_updates_success:
                    updates.append({
                        "timestamp": timestamp,
                        "message": github_comment,
                        "type": "github",
                        "confidenceScore": confidence_score
                    })
        elif test_passed:
            # Handle successful test case
            jira_comment = await self.format_agent_comment(
                "QA",
                f"✅ Bug fix tested successfully on attempt {retry_count}/{max_retries}." +
                (f" PR created: {github_pr_url}" if github_pr_url else "") +
                (f" (Confidence score: {confidence_score}%)" if confidence_score is not None else ""),
                retry_count,
                max_retries
            )
            
            # Add update for frontend
            updates.append({
                "timestamp": timestamp,
                "message": f"✅ Bug fix tested successfully on attempt {retry_count}/{max_retries}" +
                          (f" (Confidence score: {confidence_score}%)" if confidence_score is not None else ""),
                "type": "jira",
                "confidenceScore": confidence_score
            })
            
            # Update JIRA - try "Done" first since that worked in the logs
            jira_updates_success = await self._update_jira_ticket(
                ticket_id,
                "Done",  # Changed from "Resolved" to "Done" based on the logs
                jira_comment
            )
            
            # Update GitHub PR if URL provided
            if github_pr_url:
                github_comment = f"✅ All tests passed on attempt {retry_count}/{max_retries}. Ready for review."
                if confidence_score is not None:
                    github_comment += f" (Confidence score: {confidence_score}%)"
                    
                # Fixed the awaiting of the post_github_comment method
                github_updates_success = await self._post_github_comment(
                    ticket_id,
                    github_pr_url,
                    github_comment
                )
                
                if github_updates_success:
                    updates.append({
                        "timestamp": timestamp,
                        "message": github_comment,
                        "type": "github",
                        "confidenceScore": confidence_score
                    })
        elif escalated:
            # Handle escalation case after max retries
            failure_msg = ""
            if failure_details or failure_summary:
                failure_msg = f"\n\nLast failure details: {failure_details or failure_summary}"
                
            jira_comment = await self.format_agent_comment(
                "Communicator",
                f"❌ Automated fix attempts failed after {retry_count} tries. "
                f"Escalating to human reviewer.{failure_msg}",
                retry_count,
                max_retries
            )
            
            updates.append({
                "timestamp": timestamp,
                "message": f"❌ Automated fix attempts failed after {retry_count} tries. Escalating to human reviewer.",
                "type": "jira",
                "confidenceScore": confidence_score
            })
            
            # Add system message for frontend
            updates.append({
                "timestamp": timestamp,
                "message": "Ticket escalated for human review after maximum retry attempts.",
                "type": "system"
            })
            
            jira_updates_success = await self._update_jira_ticket(
                ticket_id,
                "Needs Review",
                jira_comment
            )
            
            if github_pr_url:
                github_comment = f"❌ Automated tests failed after {retry_count} retries. Escalating to human review."
                if failure_details or failure_summary:
                    github_comment += f"\n\nLast failure: {failure_details or failure_summary}"
                    
                github_updates_success = await self._post_github_comment(
                    ticket_id,
                    github_pr_url,
                    github_comment
                )
                
                if github_updates_success:
                    updates.append({
                        "timestamp": timestamp,
                        "message": github_comment,
                        "type": "github"
                    })
        else:
            # Handle test failure case with more retries left
            if retry_count < max_retries:
                # Still have retries left
                failure_msg = ""
                if failure_details:
                    failure_msg = f"\n\nFailure details: {failure_details}"
                    
                jira_comment = await self.format_agent_comment(
                    "QA",
                    f"⚠️ Attempt {retry_count}/{max_retries} failed. "
                    f"Retrying fix generation...{failure_msg}",
                    retry_count,
                    max_retries
                )
                
                updates.append({
                    "timestamp": timestamp,
                    "message": f"⚠️ Attempt {retry_count}/{max_retries} failed. Retrying fix generation.",
                    "type": "jira"
                })
                
                jira_updates_success = await self._update_jira_ticket(
                    ticket_id,
                    "In Progress",
                    jira_comment
                )
            else:
                # This should be caught by the escalated flag, but just in case
                jira_comment = await self.format_agent_comment(
                    "Communicator",
                    f"❌ Automated fix attempts failed after {max_retries} tries. "
                    "Escalating to human reviewer.",
                    max_retries,
                    max_retries
                )
                
                updates.append({
                    "timestamp": timestamp,
                    "message": f"❌ Automated fix attempts failed after {max_retries} tries. Escalating to human reviewer.",
                    "type": "jira"
                })
                
                jira_updates_success = await self._update_jira_ticket(
                    ticket_id,
                    "Needs Review",
                    jira_comment
                )
        
        # Post specific agent comments if agent_type is provided
        if agent_type in ["planner", "developer"] and not test_passed and not early_escalation and not escalated:
            agent_name = agent_type.capitalize()
            agent_message = f"{agent_name} completed analysis" if agent_type == "planner" else f"{agent_name} generated a fix (attempt {retry_count}/{max_retries})"
            
            agent_comment = await self.format_agent_comment(
                agent_name,
                agent_message,
                retry_count if agent_type == "developer" else None,
                max_retries if agent_type == "developer" else None
            )
            
            await self._update_jira_ticket(ticket_id, "", agent_comment)
            
            updates.append({
                "timestamp": timestamp,
                "message": agent_message,
                "type": "jira"
            })
        
        # Set agent status based on operation success
        self.status = (
            AgentStatus.SUCCESS 
            if jira_updates_success and github_updates_success 
            else AgentStatus.FAILED
        )
        
        # Return processing results with updates for frontend
        return {
            "ticket_id": ticket_id,
            "communications_success": jira_updates_success and github_updates_success,
            "test_passed": test_passed,
            "jira_updated": jira_updates_success,
            "github_updated": github_updates_success if github_pr_url else None,
            "github_pr_url": github_pr_url, # Add the validated PR URL to the result
            "escalated": escalated or early_escalation,
            "early_escalation": early_escalation,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "confidence_score": confidence_score,
            "updates": updates,
            "timestamp": datetime.now().isoformat()
        }
