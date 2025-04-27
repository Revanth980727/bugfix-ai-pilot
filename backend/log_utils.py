
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("log-utils")

def setup_ticket_logging(ticket_id: str) -> str:
    """Setup logging directory for a ticket and return the path"""
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    return ticket_log_dir

def log_agent_input(ticket_id: str, agent: str, data: Dict[str, Any]) -> None:
    """Log input data sent to an agent"""
    ticket_log_dir = f"logs/{ticket_id}"
    with open(f"{ticket_log_dir}/{agent}_input.json", 'w') as f:
        json.dump(data, f, indent=2)

def log_agent_output(ticket_id: str, agent: str, data: Dict[str, Any]) -> None:
    """Log output received from an agent"""
    ticket_log_dir = f"logs/{ticket_id}"
    with open(f"{ticket_log_dir}/{agent}_output.json", 'w') as f:
        json.dump(data, f, indent=2)

def log_error(ticket_id: str, agent: str, error_message: str) -> None:
    """Log an error for a specific agent"""
    error_log = {
        "timestamp": datetime.now().isoformat(),
        "message": error_message
    }
    
    ticket_log_dir = f"logs/{ticket_id}"
    with open(f"{ticket_log_dir}/{agent}_errors.json", 'a') as f:
        f.write(json.dumps(error_log) + "\n")

