
import logging
import os
from datetime import datetime
import httpx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from env import JIRA_TOKEN, JIRA_USER, JIRA_URL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jira-utils")

async def update_jira_ticket(ticket_id: str, status: str, comment: str, pr_url: Optional[str] = None) -> bool:
    """Update JIRA ticket status and add a comment"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth = (JIRA_USER, JIRA_TOKEN)
            
            # Add comment
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
            
            comment_response = await client.post(
                f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/comment",
                json=comment_data,
                auth=auth
            )
            
            if comment_response.status_code not in [200, 201]:
                logger.error(f"Failed to add comment to JIRA ticket {ticket_id}: {comment_response.status_code}")
                return False
            
            if status:
                transitions_response = await client.get(
                    f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
                    auth=auth
                )
                
                if transitions_response.status_code != 200:
                    logger.error(f"Failed to get transitions for JIRA ticket {ticket_id}")
                    return False
                
                transitions = transitions_response.json().get("transitions", [])
                transition_id = None
                
                for t in transitions:
                    if status.lower() in t['name'].lower():
                        transition_id = t['id']
                        break
                
                if transition_id:
                    transition_data = {
                        "transition": {
                            "id": transition_id
                        }
                    }
                    
                    transition_response = await client.post(
                        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
                        json=transition_data,
                        auth=auth
                    )
                    
                    if transition_response.status_code not in [200, 204]:
                        logger.error(f"Failed to transition JIRA ticket {ticket_id}")
                        return False
            
            logger.info(f"Successfully updated JIRA ticket {ticket_id}")
            return True
    
    except Exception as e:
        logger.error(f"Error updating JIRA ticket {ticket_id}: {str(e)}")
        return False

async def fetch_jira_tickets() -> List[Dict[str, Any]]:
    """Poll the JIRA API for new tickets labeled as Bug"""
    try:
        logger.info("Fetching new bug tickets from JIRA")
        auth = (JIRA_USER, JIRA_TOKEN)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            jql_query = 'labels = Bug AND status = "To Do"'
            
            response = await client.get(
                f"{JIRA_URL}/rest/api/3/search",
                params={"jql": jql_query, "fields": "summary,description,created,assignee,acceptanceCriteria,attachments,status,priority,reporter"},
                auth=auth
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch JIRA tickets: {response.status_code}")
                return []
                
            data = response.json()
            new_tickets = []
            
            for issue in data.get("issues", []):
                ticket_id = issue["key"]
                acceptance_criteria = issue["fields"].get("acceptanceCriteria", "")
                
                attachments = []
                for attachment in issue["fields"].get("attachments", []):
                    attachments.append({
                        "filename": attachment["filename"],
                        "content_url": attachment["content"],
                        "mime_type": attachment["mimeType"]
                    })
                    
                new_tickets.append({
                    "ticket_id": ticket_id,
                    "title": issue["fields"]["summary"],
                    "description": issue["fields"].get("description", ""),
                    "created": issue["fields"]["created"],
                    "acceptance_criteria": acceptance_criteria,
                    "attachments": attachments,
                    "status": issue["fields"]["status"]["name"],
                    "priority": issue["fields"]["priority"]["name"],
                    "reporter": issue["fields"]["reporter"]["displayName"],
                    "assignee": issue["fields"].get("assignee", {}).get("displayName", "Unassigned")
                })
            
            logger.info(f"Found {len(new_tickets)} new bug tickets")
            return new_tickets
    except Exception as e:
        logger.error(f"Error fetching JIRA tickets: {str(e)}")
        return []

