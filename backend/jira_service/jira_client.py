
import time
import logging
import httpx
from typing import List, Dict, Any, Optional
from . import config

logger = logging.getLogger('jira-service.client')

class JiraClient:
    def __init__(self):
        """Initialize the JIRA client with configuration"""
        self.base_url = config.JIRA_URL
        self.auth = (config.JIRA_USERNAME, config.JIRA_API_TOKEN)
        self.max_retries = config.MAX_RETRIES
        self.backoff_factor = config.RETRY_BACKOFF_FACTOR
        
        if not all([self.base_url, self.auth[0], self.auth[1]]):
            logger.error("JIRA client initialization failed: missing required configuration")
            raise ValueError("Missing required JIRA configuration")
            
        logger.info(f"JIRA client initialized for {self.base_url}")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make a request to the JIRA API with retries and exponential backoff"""
        url = f"{self.base_url}{endpoint}"
        retries = 0
        
        while retries <= self.max_retries:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await getattr(client, method.lower())(
                        url,
                        auth=self.auth,
                        **kwargs
                    )
                    
                    if response.status_code in [200, 201, 204]:
                        if method.lower() in ['get', 'post']:
                            return response.json()
                        return {"status": "success"}
                    
                    if 400 <= response.status_code < 500:
                        error_data = response.json() if response.text else {"error": "Unknown client error"}
                        logger.error(f"JIRA API client error: {response.status_code}, {error_data}")
                        return None
                    
                    # Server error, retry with backoff
                    logger.warning(f"JIRA API server error: {response.status_code}, retrying...")
                    
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.warning(f"JIRA request failed: {str(e)}, retrying...")
            
            # Exponential backoff
            retries += 1
            if retries <= self.max_retries:
                sleep_time = self.backoff_factor ** retries
                logger.info(f"Retrying in {sleep_time} seconds (attempt {retries}/{self.max_retries})")
                time.sleep(sleep_time)
        
        logger.error(f"Failed to make JIRA request after {self.max_retries} retries")
        return None
    
    async def fetch_bug_tickets(self) -> List[Dict[str, Any]]:
        """Fetch bug tickets from JIRA that are in 'To Do' or 'Open' status"""
        logger.info("Fetching bug tickets from JIRA")
        
        # Build JQL query
        jql_parts = ["issuetype = Bug"]
        jql_parts.append('(status = "To Do" OR status = Open)')
        
        if config.JIRA_PROJECT_KEY:
            jql_parts.append(f'project = {config.JIRA_PROJECT_KEY}')
            
        jql_query = " AND ".join(jql_parts)
        
        fields = "summary,description,status,issuetype,created,updated,assignee,reporter,priority"
        params = {"jql": jql_query, "fields": fields}
        
        response = await self._make_request("GET", "/rest/api/3/search", params=params)
        
        if not response:
            logger.error("Failed to fetch bug tickets")
            return []
        
        tickets = []
        # Fix: Check if 'issues' key exists in response
        issues = response.get("issues")
        if not issues:
            logger.info("No issues found in JIRA response")
            return []
            
        for issue in issues:
            ticket = {
                "ticket_id": issue["key"],
                "title": issue["fields"]["summary"],
                "description": issue["fields"].get("description", ""),
                "status": issue["fields"]["status"]["name"],
                "created": issue["fields"]["created"],
                "updated": issue["fields"]["updated"],
                # Fix: Safely handle missing assignee
                "assignee": issue["fields"].get("assignee", {}).get("displayName", "Unassigned") if issue["fields"].get("assignee") else "Unassigned",
                # Fix: Safely handle missing reporter
                "reporter": issue["fields"].get("reporter", {}).get("displayName", "Unknown") if issue["fields"].get("reporter") else "Unknown",
                # Fix: Safely handle missing priority
                "priority": issue["fields"].get("priority", {}).get("name", "Normal") if issue["fields"].get("priority") else "Normal"
            }
            tickets.append(ticket)
            
        logger.info(f"Found {len(tickets)} bug tickets to process")
        return tickets
    
    async def update_ticket_status(self, ticket_id: str, status: str) -> bool:
        """Update the status of a JIRA ticket"""
        logger.info(f"Updating ticket {ticket_id} status to '{status}'")
        
        # First, get available transitions
        transitions_response = await self._make_request(
            "GET", 
            f"/rest/api/3/issue/{ticket_id}/transitions"
        )
        
        if not transitions_response:
            logger.error(f"Failed to get transitions for ticket {ticket_id}")
            return False
        
        # Find the transition ID for the target status
        transition_id = None
        transitions = transitions_response.get("transitions", [])
        for transition in transitions:
            if status.lower() in transition["name"].lower():
                transition_id = transition["id"]
                break
        
        if not transition_id:
            logger.error(f"No transition found for status '{status}' in ticket {ticket_id}")
            return False
        
        # Perform the transition
        transition_data = {
            "transition": {
                "id": transition_id
            }
        }
        
        result = await self._make_request(
            "POST",
            f"/rest/api/3/issue/{ticket_id}/transitions",
            json=transition_data
        )
        
        success = result is not None
        if success:
            logger.info(f"Successfully updated ticket {ticket_id} status to '{status}'")
        else:
            logger.error(f"Failed to update ticket {ticket_id} status")
        
        return success
    
    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        """Add a comment to a JIRA ticket"""
        logger.info(f"Adding comment to ticket {ticket_id}")
        
        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": comment
                    }]
                }]
            }
        }
        
        result = await self._make_request(
            "POST",
            f"/rest/api/3/issue/{ticket_id}/comment",
            json=comment_data
        )
        
        success = result is not None
        if success:
            logger.info(f"Successfully added comment to ticket {ticket_id}")
        else:
            logger.error(f"Failed to add comment to ticket {ticket_id}")
        
        return success

    async def update_ticket(self, ticket_id: str, status: Optional[str] = None, comment: Optional[str] = None) -> bool:
        """Update a JIRA ticket with new status and/or comment"""
        success = True
        
        if comment:
            comment_success = await self.add_comment(ticket_id, comment)
            success = success and comment_success
        
        if status:
            status_success = await self.update_ticket_status(ticket_id, status)
            success = success and status_success
        
        return success

