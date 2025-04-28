
import os
import json
import requests
from typing import Dict, Any, List, Optional, Union
from .logger import Logger

class JiraClient:
    """Client for interacting with JIRA REST API"""
    
    def __init__(self):
        """Initialize JIRA client with environment variables"""
        self.logger = Logger("jira_client")
        
        # Get credentials from environment variables
        self.jira_url = os.environ.get("JIRA_URL")
        self.jira_user = os.environ.get("JIRA_USER")
        self.jira_token = os.environ.get("JIRA_TOKEN")
        self.project_key = os.environ.get("JIRA_PROJECT_KEY", "")
        
        if not all([self.jira_url, self.jira_user, self.jira_token]):
            self.logger.error("Missing required JIRA environment variables")
            raise EnvironmentError(
                "Missing JIRA credentials. Please set JIRA_URL, JIRA_USER, and JIRA_TOKEN environment variables."
            )
            
        # Set up auth and headers
        self.auth = (self.jira_user, self.jira_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
    def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """
        Fetch a JIRA ticket by ID
        
        Args:
            ticket_id: The JIRA ticket ID (e.g., "PROJ-123")
            
        Returns:
            Dictionary containing ticket data
        """
        url = f"{self.jira_url}/rest/api/3/issue/{ticket_id}"
        
        self.logger.info(f"Fetching ticket {ticket_id}")
        response = requests.get(
            url, 
            auth=self.auth, 
            headers=self.headers
        )
        
        if response.status_code != 200:
            self.logger.error(f"Failed to fetch ticket {ticket_id}: {response.status_code}, {response.text}")
            response.raise_for_status()
            
        return response.json()
    
    def get_open_bugs(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch open bug tickets from JIRA
        
        Args:
            max_results: Maximum number of tickets to return
            
        Returns:
            List of ticket dictionaries
        """
        url = f"{self.jira_url}/rest/api/3/search"
        
        # Build JQL query for open bugs
        project_clause = f"project = {self.project_key}" if self.project_key else ""
        jql = f"type = Bug AND status in ('Open', 'To Do') {project_clause}"
        
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,description,status,created,updated"
        }
        
        self.logger.info(f"Fetching open bugs with JQL: {jql}")
        response = requests.get(
            url,
            params=params,
            auth=self.auth,
            headers=self.headers
        )
        
        if response.status_code != 200:
            self.logger.error(f"Failed to fetch open bugs: {response.status_code}, {response.text}")
            response.raise_for_status()
        
        data = response.json()
        tickets = []
        
        for issue in data.get("issues", []):
            ticket_id = issue["key"]
            tickets.append({
                "ticket_id": ticket_id,
                "title": issue["fields"]["summary"],
                "description": issue["fields"].get("description", ""),
                "status": issue["fields"]["status"]["name"],
                "created": issue["fields"]["created"],
                "updated": issue["fields"].get("updated", "")
            })
            
        self.logger.info(f"Found {len(tickets)} open bug tickets")
        return tickets
    
    def add_comment(self, ticket_id: str, comment: str) -> bool:
        """
        Add a comment to a JIRA ticket
        
        Args:
            ticket_id: The JIRA ticket ID
            comment: Comment text (can contain JIRA markdown)
            
        Returns:
            Success status (True/False)
        """
        url = f"{self.jira_url}/rest/api/3/issue/{ticket_id}/comment"
        
        # Format for JIRA API
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment
                            }
                        ]
                    }
                ]
            }
        }
        
        self.logger.info(f"Adding comment to ticket {ticket_id}")
        response = requests.post(
            url,
            json=payload,
            auth=self.auth,
            headers=self.headers
        )
        
        if response.status_code not in (201, 200):
            self.logger.error(f"Failed to add comment to {ticket_id}: {response.status_code}, {response.text}")
            return False
            
        self.logger.info(f"Comment added to {ticket_id} successfully")
        return True
    
    def update_ticket(self, ticket_id: str, status: str, comment: Optional[str] = None) -> bool:
        """
        Update a JIRA ticket status and optionally add a comment
        
        Args:
            ticket_id: The JIRA ticket ID
            status: The new status to set
            comment: Optional comment to add
            
        Returns:
            Success status (True/False)
        """
        # First, get the list of available transitions
        transitions_url = f"{self.jira_url}/rest/api/3/issue/{ticket_id}/transitions"
        
        self.logger.info(f"Fetching available transitions for {ticket_id}")
        transitions_response = requests.get(
            transitions_url,
            auth=self.auth,
            headers=self.headers
        )
        
        if transitions_response.status_code != 200:
            self.logger.error(f"Failed to get transitions for {ticket_id}: {transitions_response.status_code}")
            return False
            
        transitions = transitions_response.json().get("transitions", [])
        transition_id = None
        
        # Find the transition that matches our target status
        for transition in transitions:
            if transition["to"]["name"].lower() == status.lower():
                transition_id = transition["id"]
                break
                
        if not transition_id:
            self.logger.error(f"No transition found for status '{status}' on ticket {ticket_id}")
            return False
            
        # Perform the transition
        transition_payload = {
            "transition": {
                "id": transition_id
            }
        }
        
        self.logger.info(f"Updating ticket {ticket_id} to status '{status}'")
        transition_result = requests.post(
            transitions_url,
            json=transition_payload,
            auth=self.auth,
            headers=self.headers
        )
        
        if transition_result.status_code not in (204, 200):
            self.logger.error(f"Failed to update status for {ticket_id}: {transition_result.status_code}")
            return False
            
        # Add comment if provided
        if comment:
            comment_result = self.add_comment(ticket_id, comment)
            if not comment_result:
                self.logger.warning(f"Status updated but failed to add comment to {ticket_id}")
                return False
                
        self.logger.info(f"Successfully updated ticket {ticket_id} to '{status}'")
        return True
