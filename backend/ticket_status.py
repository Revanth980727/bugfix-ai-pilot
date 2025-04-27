
from typing import Dict, Any, List
from datetime import datetime

# Store active tickets
active_tickets: Dict[str, Dict[str, Any]] = {}

def initialize_ticket(ticket_id: str, ticket: Dict[str, Any]) -> None:
    """Initialize a new ticket in the active_tickets tracker"""
    active_tickets[ticket_id] = {
        "ticket_id": ticket_id,
        "status": "planning",  # Changed initial status to be more specific
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "title": ticket["title"],
        "description": ticket["description"],
        "acceptance_criteria": ticket.get("acceptance_criteria", ""),
        "attachments": ticket.get("attachments", []),
        "planner_analysis": None,
        "developer_diffs": None,
        "qa_results": None,
        "communicator_result": None,
        "current_attempt": 1,
        "max_attempts": 4,
        "retry_history": [],
        "qa_failures": []
    }

def update_ticket_status(ticket_id: str, status: str, data: Dict[str, Any] = None) -> None:
    """Update ticket status and optionally add data"""
    if ticket_id in active_tickets:
        active_tickets[ticket_id]["status"] = status
        active_tickets[ticket_id]["last_updated"] = datetime.now().isoformat()
        if data:
            if "qa_failure" in data:
                active_tickets[ticket_id]["qa_failures"].append({
                    "attempt": active_tickets[ticket_id]["current_attempt"],
                    "timestamp": datetime.now().isoformat(),
                    "details": data["qa_failure"]
                })
            active_tickets[ticket_id].update(data)

def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
    """Get current status of a ticket"""
    return active_tickets.get(ticket_id, {})

def get_retry_info(ticket_id: str) -> Dict[str, Any]:
    """Get retry information for a ticket"""
    if ticket_id not in active_tickets:
        return {}
        
    ticket = active_tickets[ticket_id]
    return {
        "current_attempt": ticket["current_attempt"],
        "max_attempts": ticket["max_attempts"],
        "qa_failures": ticket["qa_failures"],
        "can_retry": ticket["current_attempt"] < ticket["max_attempts"]
    }

def cleanup_old_tickets() -> None:
    """Clean up completed/error tickets older than 1 hour"""
    current_time = datetime.now()
    tickets_to_remove = []
    
    for ticket_id, ticket_data in active_tickets.items():
        if ticket_data["status"] in ["completed", "error"]:
            started_at = datetime.fromisoformat(ticket_data["started_at"])
            if (current_time - started_at).total_seconds() > 3600:  # 1 hour
                tickets_to_remove.append(ticket_id)
                
    for ticket_id in tickets_to_remove:
        del active_tickets[ticket_id]

