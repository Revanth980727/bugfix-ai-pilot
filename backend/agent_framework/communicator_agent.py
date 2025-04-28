
from typing import Dict, Any, Optional
import logging
from datetime import datetime
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
        
    async def _update_jira_ticket(self, ticket_id: str, status: str, comment: str) -> bool:
        """Update JIRA ticket with status and comment"""
        try:
            success = await self.jira_client.update_ticket(ticket_id, status, comment)
            if success:
                logger.info(f"Successfully updated JIRA ticket {ticket_id}")
            else:
                logger.error(f"Failed to update JIRA ticket {ticket_id}")
            return success
        except Exception as e:
            logger.error(f"Error updating JIRA ticket {ticket_id}: {str(e)}")
            return False
            
    async def _post_github_comment(self, pr_url: str, comment: str) -> bool:
        """Post a comment on GitHub PR"""
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
            else:
                logger.error(f"Failed to add comment to PR {pr_url}")
            return success
        except Exception as e:
            logger.error(f"Error posting GitHub comment: {str(e)}")
            return False

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process communication tasks based on test results"""
        ticket_id = input_data.get("ticket_id")
        test_passed = input_data.get("test_passed", False)
        github_pr_url = input_data.get("github_pr_url")
        retry_count = input_data.get("retry_count", 0)
        max_retries = input_data.get("max_retries", 4)
        escalated = input_data.get("escalated", False)
        
        if not ticket_id:
            raise ValueError("ticket_id is required")
        
        self.log(f"Processing communication for ticket {ticket_id}")
        
        jira_updates_success = True
        github_updates_success = True
        updates = []
        
        # Timestamp for updates
        timestamp = datetime.now().isoformat()
        
        if test_passed:
            # Handle successful test case
            jira_comment = f"✅ Bug fix tested successfully on attempt {retry_count}/{max_retries}."
            if github_pr_url:
                jira_comment += f" PR created: {github_pr_url}"
            
            # Add update for frontend
            updates.append({
                "timestamp": timestamp,
                "message": jira_comment,
                "type": "jira"
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
        elif escalated:
            # Handle escalation case
            jira_comment = (
                f"❌ Automated fix attempts failed after {max_retries} tries. "
                "Escalating to human reviewer."
            )
            
            updates.append({
                "timestamp": timestamp,
                "message": jira_comment,
                "type": "jira"
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
                github_comment = f"❌ Automated tests failed after {max_retries} retries. Escalating to human review."
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
                jira_comment = (
                    f"⚠️ Attempt {retry_count}/{max_retries} failed. "
                    "Retrying fix generation..."
                )
                
                updates.append({
                    "timestamp": timestamp,
                    "message": jira_comment,
                    "type": "jira"
                })
                
                jira_updates_success = await self._update_jira_ticket(
                    ticket_id,
                    "In Progress",
                    jira_comment
                )
            else:
                # This should be caught by the escalated flag, but just in case
                jira_comment = (
                    f"❌ Automated fix attempts failed after {max_retries} tries. "
                    "Escalating to human reviewer."
                )
                
                updates.append({
                    "timestamp": timestamp,
                    "message": jira_comment,
                    "type": "jira"
                })
                
                jira_updates_success = await self._update_jira_ticket(
                    ticket_id,
                    "Needs Review",
                    jira_comment
                )
        
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
            "escalated": escalated,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "updates": updates,
            "timestamp": datetime.now().isoformat()
        }

