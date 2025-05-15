
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import traceback

# Configure the default logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create a logger factory
class LoggerFactory:
    def __init__(self):
        self.loggers = {}
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the specified name"""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
        return self.loggers[name]

# Create a singleton instance
logger = LoggerFactory()

def setup_ticket_logging(ticket_id: str) -> str:
    """Setup logging directory for a ticket and return the path"""
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    
    # Create structured log file for the ticket
    structured_log_path = f"{ticket_log_dir}/ticket_log.jsonl"
    if not os.path.exists(structured_log_path):
        with open(structured_log_path, 'w') as f:
            f.write("")
            
    return ticket_log_dir

def log_action(ticket_id: str, agent: str, action: str, output: Optional[Dict[str, Any]] = None, 
               error: Optional[str] = None, level: str = "INFO") -> None:
    """Log an action with structured data"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "ticket_id": ticket_id,
        "agent": agent,
        "action": action,
        "level": level.upper(),
        "output": output
    }
    
    if error:
        log_entry["error"] = error
        log_entry["stacktrace"] = traceback.format_exc()
    
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    
    with open(f"{ticket_log_dir}/ticket_log.jsonl", 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

def log_agent_input(ticket_id: str, agent: str, data: Dict[str, Any]) -> None:
    """Log input data sent to an agent"""
    log_action(ticket_id, agent, "input", data)
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    
    with open(f"{ticket_log_dir}/{agent}_input.json", 'w') as f:
        json.dump(data, f, indent=2)

def log_agent_output(ticket_id: str, agent: str, data: Dict[str, Any]) -> None:
    """Log output received from an agent"""
    log_action(ticket_id, agent, "output", data)
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    
    with open(f"{ticket_log_dir}/{agent}_output.json", 'w') as f:
        json.dump(data, f, indent=2)

def log_error(ticket_id: str, agent: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Log an error for a specific agent"""
    log_action(ticket_id, agent, "error", details, error_message, "ERROR")
    error_log = {
        "timestamp": datetime.now().isoformat(),
        "message": error_message,
        "details": details
    }
    
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    
    with open(f"{ticket_log_dir}/{agent}_errors.json", 'a') as f:
        f.write(json.dumps(error_log) + "\n")
        
def log_github_operation(ticket_id: str, operation: str, details: Dict[str, Any], success: bool = True) -> None:
    """Log a GitHub operation like PR creation, commit, etc."""
    status = "success" if success else "failure"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "ticket_id": ticket_id,
        "operation": operation,
        "status": status,
        "details": details
    }
    
    ticket_log_dir = f"logs/{ticket_id}"
    os.makedirs(ticket_log_dir, exist_ok=True)
    
    with open(f"{ticket_log_dir}/github_operations.jsonl", 'a') as f:
        f.write(json.dumps(log_entry) + "\n")

def get_operation_logs(ticket_id: str, operation_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get operation logs for a specific ticket"""
    ticket_log_dir = f"logs/{ticket_id}"
    log_file = f"{ticket_log_dir}/github_operations.jsonl"
    
    if not os.path.exists(log_file):
        return []
        
    logs = []
    with open(log_file, 'r') as f:
        for line in f:
            try:
                log_entry = json.loads(line.strip())
                if operation_type is None or log_entry.get("operation") == operation_type:
                    logs.append(log_entry)
            except:
                continue
                
    return logs

def log_diff(ticket_id: str, filename: str, diff: str, lines_added: int, lines_removed: int) -> None:
    """Log a diff for debugging purposes"""
    log_file = f"logs/{ticket_id}/diffs/{filename.replace('/', '_')}.diff"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    with open(log_file, 'w') as f:
        f.write(f"# Diff for {filename}\n")
        f.write(f"# Lines added: {lines_added}, Lines removed: {lines_removed}\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
        f.write(diff)
        
    # Also log basic info to the main log
    log_action(ticket_id, "diff_generator", "generate_diff", {
        "filename": filename,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "diff_length": len(diff)
    })
