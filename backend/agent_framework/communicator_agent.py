from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime
import time
from .agent_base import Agent, AgentStatus
from ..jira_service.jira_client import JiraClient
from ..github_service.github_service import GitHubService
from ..env import verify_github_repo_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator-agent")

class CommunicatorAgent(Agent):
    def __init__(self):
        super().__init__(name="CommunicatorAgent")
        self.jira_client = JiraClient()
        self.github_service = GitHubService()
        self.max_api_retries = 3  # Maximum retries for API calls
        
    async def _update_jira_ticket(self, ticket_id: str, status: str, comment: str) -> bool:
        """Update JIRA ticket with status and comment with retry logic"""
        retry_count = 0
        while retry_count < self.max_api_retries:
            try:
                success = await self.jira_client.update_ticket(ticket_id, status, comment)
                if success:
                    logger.info(f"Successfully updated JIRA ticket {ticket_id}")
                    return success
                else:
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
            
    async def _post_github_comment(self, pr_url: str, comment: str) -> bool:
        """Post a comment on GitHub PR with retry logic"""
        retry_count = 0
        while retry_count < self.max_api_retries:
            try:
                # Extract PR number from URL
                pr_number = pr_url.split('/')[-1]
                
                # Verify GitHub settings
                github_ok, _ = verify_github_repo_settings()
                if not github_ok:
                    logger.error("GitHub settings are not properly configured")
                    return False
                    
                # Post comment using GitHub service
                success = await self.github_service.add_pr_comment(pr_number, comment)
                if success:
                    logger.info(f"Successfully added comment to PR {pr_url}")
                    return success
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
        
        if not ticket_id:
            raise ValueError("ticket_id is required")
        
        self.log(f"Processing communication for ticket {ticket_id}")
        
        jira_updates_success = True
        github_updates_success = True
        updates = []
        
        # Timestamp for updates
        timestamp = datetime.now().isoformat()
        
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
            
            # Update JIRA
            jira_updates_success = await self._update_jira_ticket(
                ticket_id,
                "Resolved",
                jira_comment
            )
            
            # Update GitHub PR if URL provided
            if github_pr_url:
                github_comment = f"✅ All tests passed on attempt {retry_count}/{max_retries}. Ready for review."
                if confidence_score is not None:
                    github_comment += f" (Confidence score: {confidence_score}%)"
                    
                github_updates_success = await self._post_github_comment(
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
            "escalated": escalated or early_escalation,
            "early_escalation": early_escalation,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "confidence_score": confidence_score,
            "updates": updates,
            "timestamp": datetime.now().isoformat()
        }
