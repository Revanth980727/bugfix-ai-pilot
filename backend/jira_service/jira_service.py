
import os
import logging
import json
import requests
from typing import Dict, Any, Optional, List, Tuple
import time

class JiraService:
    """Service for interacting with JIRA"""
    
    def __init__(self):
        """Initialize the JIRA service"""
        self.logger = logging.getLogger("jira-service")
        
        # Get JIRA credentials from environment variables
        self.jira_url = os.environ.get("JIRA_URL")
        self.jira_user = os.environ.get("JIRA_USER")
        self.jira_token = os.environ.get("JIRA_TOKEN")
        self.test_mode = os.environ.get("JIRA_TEST_MODE", "false").lower() == "true"
        
        # Check if we have the necessary credentials
        self.is_configured = all([self.jira_url, self.jira_user, self.jira_token])
        if not self.is_configured:
            self.logger.warning("JIRA service not fully configured. Some features will be limited.")
        else:
            self.logger.info("JIRA service initialized")
            
        # Set up authentication and headers
        if self.is_configured:
            self.auth = (self.jira_user, self.jira_token)
            self.headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
    
    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get ticket details from JIRA
        
        Args:
            ticket_id: JIRA ticket ID
            
        Returns:
            Ticket details or None if unsuccessful
        """
        if not self.is_configured and not self.test_mode:
            self.logger.warning("Cannot get ticket: JIRA service not configured")
            return None
            
        # If in test mode, return mock data
        if self.test_mode:
            self.logger.info(f"Test mode: Returning mock data for ticket {ticket_id}")
            return {
                "id": "12345",
                "key": ticket_id,
                "fields": {
                    "summary": f"Mock ticket for {ticket_id}",
                    "description": "This is a mock ticket for testing",
                    "status": {
                        "name": "Open"
                    }
                }
            }
            
        # Make the API request
        url = f"{self.jira_url}/rest/api/2/issue/{ticket_id}"
        
        try:
            self.logger.info(f"Getting ticket {ticket_id}")
            response = requests.get(url, auth=self.auth, headers=self.headers)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to get ticket {ticket_id}: {response.status_code}")
                return None
                
            ticket_data = response.json()
            self.logger.info(f"Successfully retrieved ticket {ticket_id}")
            return ticket_data
        except Exception as e:
            self.logger.error(f"Error getting ticket {ticket_id}: {e}")
            return None
    
    def update_ticket_status(self, ticket_id: str, status: str, comment: Optional[str] = None) -> bool:
        """
        Update a ticket's status in JIRA
        
        Args:
            ticket_id: JIRA ticket ID
            status: Target status
            comment: Optional comment to add
            
        Returns:
            Success status
        """
        if not self.is_configured and not self.test_mode:
            self.logger.warning(f"Cannot update ticket {ticket_id}: JIRA service not configured")
            return False
            
        # If in test mode, log and return success
        if self.test_mode:
            self.logger.info(f"Test mode: Simulating status update for ticket {ticket_id} to {status}")
            if comment:
                self.logger.info(f"Test mode: Would add comment to {ticket_id}: {comment[:50]}...")
            return True
            
        # First get the available transitions
        transitions_url = f"{self.jira_url}/rest/api/2/issue/{ticket_id}/transitions"
        
        try:
            self.logger.info(f"Getting available transitions for {ticket_id}")
            transitions_response = requests.get(transitions_url, auth=self.auth, headers=self.headers)
            
            if transitions_response.status_code != 200:
                self.logger.error(f"Failed to get transitions for {ticket_id}: {transitions_response.status_code}")
                return False
                
            transitions = transitions_response.json().get("transitions", [])
            target_transition = None
            
            # Find the transition that matches the target status
            for transition in transitions:
                if transition.get("to", {}).get("name", "").lower() == status.lower():
                    target_transition = transition
                    break
                    
            # If no exact match, try to find a transition with a similar name
            if not target_transition:
                for transition in transitions:
                    if status.lower() in transition.get("name", "").lower():
                        target_transition = transition
                        break
                        
            if not target_transition:
                self.logger.error(f"No transition found for status {status}")
                return False
                
            # Apply the transition
            transition_data = {
                "transition": {
                    "id": target_transition.get("id")
                }
            }
            
            self.logger.info(f"Updating ticket {ticket_id} status to {status}")
            transition_response = requests.post(
                transitions_url,
                auth=self.auth,
                headers=self.headers,
                json=transition_data
            )
            
            if transition_response.status_code not in [200, 204]:
                self.logger.error(f"Failed to update status for {ticket_id}: {transition_response.status_code}")
                return False
                
            # Add comment if provided
            if comment:
                self.add_comment(ticket_id, comment)
                
            self.logger.info(f"Successfully updated ticket {ticket_id} status to {status}")
            return True
        except Exception as e:
            self.logger.error(f"Error updating ticket {ticket_id} status: {e}")
            return False
    
    def add_comment(self, ticket_id: str, comment: str) -> bool:
        """
        Add a comment to a JIRA ticket
        
        Args:
            ticket_id: JIRA ticket ID
            comment: Comment text
            
        Returns:
            Success status
        """
        if not self.is_configured and not self.test_mode:
            self.logger.warning(f"Cannot add comment to {ticket_id}: JIRA service not configured")
            return False
            
        # If in test mode, log and return success
        if self.test_mode:
            self.logger.info(f"Test mode: Simulating comment addition to {ticket_id}: {comment[:50]}...")
            return True
            
        # Make the API request
        url = f"{self.jira_url}/rest/api/2/issue/{ticket_id}/comment"
        
        try:
            comment_data = {
                "body": comment
            }
            
            self.logger.info(f"Adding comment to ticket {ticket_id}")
            response = requests.post(url, auth=self.auth, headers=self.headers, json=comment_data)
            
            if response.status_code not in [200, 201]:
                self.logger.error(f"Failed to add comment to {ticket_id}: {response.status_code}")
                return False
                
            self.logger.info(f"Successfully added comment to ticket {ticket_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error adding comment to {ticket_id}: {e}")
            return False
            
    def update_ticket_with_pr(self, ticket_id: str, pr_url: str, pr_number: int, qa_passed: bool = True, comment: Optional[str] = None) -> bool:
        """
        Update a ticket with PR information and set appropriate status
        
        Args:
            ticket_id: JIRA ticket ID
            pr_url: Pull request URL
            pr_number: Pull request number
            qa_passed: Whether QA tests passed
            comment: Optional additional comment text
            
        Returns:
            Success status
        """
        # Generate appropriate status based on test results
        target_status = "In Review" if qa_passed else "QA Failed"
        
        # Create comment with PR info
        pr_comment = f"Pull request created: [PR #{pr_number}|{pr_url}]\n"
        
        if qa_passed:
            pr_comment += "QA tests passed. Ready for review."
        else:
            pr_comment += "QA tests failed. See the PR for details."
            
        if comment:
            pr_comment += f"\n\n{comment}"
            
        # Add the comment first
        self.add_comment(ticket_id, pr_comment)
        
        # Then update the status
        return self.update_ticket_status(ticket_id, target_status)
        
    def update_ticket_with_commit(self, ticket_id: str, commit_info: Dict[str, Any], qa_passed: bool = True) -> bool:
        """
        Update a ticket with commit information and set appropriate status
        
        Args:
            ticket_id: JIRA ticket ID
            commit_info: Information about the commit
            qa_passed: Whether QA tests passed
            
        Returns:
            Success status
        """
        # Create comment with commit info
        files_changed = commit_info.get("files_changed", 0)
        branch = commit_info.get("branch", "unknown")
        
        commit_comment = f"Changes committed to branch {branch}. {files_changed} files changed.\n"
        
        if qa_passed:
            commit_comment += "QA tests passed."
            target_status = "In Progress"
        else:
            commit_comment += "QA tests failed."
            target_status = "QA Failed"
            
        # Add the comment first
        self.add_comment(ticket_id, commit_comment)
        
        # Then update the status
        return self.update_ticket_status(ticket_id, target_status)
        
    def check_ticket_exists(self, ticket_id: str) -> bool:
        """
        Check if a ticket exists in JIRA
        
        Args:
            ticket_id: JIRA ticket ID
            
        Returns:
            True if the ticket exists, False otherwise
        """
        ticket = self.get_ticket(ticket_id)
        return ticket is not None
        
    def get_ticket_status(self, ticket_id: str) -> Optional[str]:
        """
        Get the current status of a ticket
        
        Args:
            ticket_id: JIRA ticket ID
            
        Returns:
            Status name or None if unsuccessful
        """
        ticket = self.get_ticket(ticket_id)
        
        if ticket:
            return ticket.get("fields", {}).get("status", {}).get("name")
        
        return None
