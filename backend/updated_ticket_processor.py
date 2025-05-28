
import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any
from .repo_manager import repo_manager
from .agent_framework.enhanced_planner_agent import EnhancedPlannerAgent
from .agent_framework.enhanced_developer_agent import EnhancedDeveloperAgent
from .agent_framework.enhanced_qa_agent import EnhancedQAAgent
from .github_service.github_client import GitHubClient

logger = logging.getLogger("ticket-processor")

# Track active tickets
active_tickets = set()

async def process_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Process a ticket using the enhanced agent workflow"""
    ticket_id = ticket.get("ticket_id", "unknown")
    
    # Add to active tickets
    active_tickets.add(ticket_id)
    
    try:
        logger.info(f"Starting enhanced processing for ticket {ticket_id}")
        
        # Ensure repository is cloned
        if not repo_manager.clone_repository():
            raise Exception("Failed to initialize repository")
        
        # Step 1: Planner Agent - Analyze ticket
        logger.info(f"Step 1: Running planner agent for {ticket_id}")
        planner_agent = EnhancedPlannerAgent()
        planner_output = planner_agent.run(ticket)
        
        if planner_agent.status.value != "success":
            raise Exception("Planner agent failed")
        
        # Step 2: Developer Agent - Generate fixes
        logger.info(f"Step 2: Running developer agent for {ticket_id}")
        developer_agent = EnhancedDeveloperAgent()
        developer_output = developer_agent.run(planner_output)
        
        if developer_agent.status.value != "success":
            raise Exception("Developer agent failed")
        
        # Step 3: QA Agent - Test fixes
        logger.info(f"Step 3: Running QA agent for {ticket_id}")
        qa_agent = EnhancedQAAgent()
        qa_output = qa_agent.run(developer_output)
        
        # Step 4: GitHub Integration - Commit if tests pass
        if qa_output.get("passed", False):
            logger.info(f"Step 4: Committing changes for {ticket_id}")
            github_client = GitHubClient()
            
            # Create branch
            branch_name = f"bugfix/{ticket_id.lower()}"
            github_client.create_branch(branch_name)
            
            # Commit changes
            changes = []
            for file_path, content in developer_output.get("patched_code", {}).items():
                changes.append({
                    "path": file_path,
                    "content": content
                })
            
            commit_result = github_client.commit_changes(
                branch_name, 
                changes, 
                f"Fix for {ticket_id}: {planner_output.get('bug_summary', 'Bug fix')}"
            )
            
            if commit_result.get("committed"):
                # Create pull request
                pr_url = github_client.create_pull_request(
                    branch_name,
                    f"Fix for {ticket_id}",
                    f"Automated fix for ticket {ticket_id}\n\n{planner_output.get('bug_summary', '')}"
                )
                
                result = {
                    "ticket_id": ticket_id,
                    "status": "success",
                    "planner_output": planner_output,
                    "developer_output": developer_output,
                    "qa_output": qa_output,
                    "pr_url": pr_url
                }
            else:
                result = {
                    "ticket_id": ticket_id,
                    "status": "failed",
                    "error": "Failed to commit changes",
                    "planner_output": planner_output,
                    "developer_output": developer_output,
                    "qa_output": qa_output
                }
        else:
            result = {
                "ticket_id": ticket_id,
                "status": "failed",
                "error": "QA tests failed",
                "planner_output": planner_output,
                "developer_output": developer_output,
                "qa_output": qa_output
            }
        
        # Log the complete result
        log_file = f"logs/{ticket_id}/complete_result.json"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Completed processing for ticket {ticket_id}: {result['status']}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
        return {
            "ticket_id": ticket_id,
            "status": "error",
            "error": str(e)
        }
    finally:
        # Remove from active tickets
        active_tickets.discard(ticket_id)

async def cleanup_old_tickets():
    """Clean up old ticket processing data"""
    # Implementation for cleanup
    pass
