
import logging
import asyncio
import os
import json
from datetime import datetime
from typing import Dict, Any
from jira_utils import update_jira_ticket
from agent_utils import (
    call_planner_agent,
    call_developer_agent,
    call_qa_agent,
    call_communicator_agent
)
from env import MAX_RETRIES
from test_processor import process_qa_results
from ticket_status import (
    active_tickets,
    initialize_ticket,
    update_ticket_status,
    cleanup_old_tickets
)
from log_utils import (
    setup_ticket_logging,
    log_agent_input,
    log_agent_output,
    log_error
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticket-processor")

async def process_ticket(ticket: Dict[str, Any]):
    """Process a single ticket through the entire agent workflow"""
    ticket_id = ticket["ticket_id"]
    
    try:
        # Setup logging and initialize ticket
        ticket_log_dir = setup_ticket_logging(ticket_id)
        initialize_ticket(ticket_id, ticket)
        
        # Log the input received
        with open(f"{ticket_log_dir}/controller_input.json", 'w') as f:
            json.dump(ticket, f, indent=2)
        
        logger.info(f"Starting processing for ticket {ticket_id}")
        
        # Update JIRA ticket to "In Progress"
        await update_jira_ticket(
            ticket_id, 
            "In Progress", 
            "BugFix AI has started working on this ticket."
        )
        
        # Step 1: Planner Analysis
        logger.info(f"Sending ticket {ticket_id} to Planner agent")
        await update_jira_ticket(ticket_id, "", "Planner analyzing bug")
        
        log_agent_input(ticket_id, "planner", ticket)
        planner_analysis = await call_planner_agent(ticket)
        
        if planner_analysis:
            log_agent_output(ticket_id, "planner", planner_analysis)
        else:
            log_error(ticket_id, "planner", "Planner analysis failed")
            update_ticket_status(ticket_id, "error")
            await update_jira_ticket(
                ticket_id,
                "",
                "BugFix AI: Planner analysis failed. Escalating to human review."
            )
            return
            
        update_ticket_status(ticket_id, "processing", {"planner_analysis": planner_analysis})
        
        # Step 2-4: Developer-QA Loop
        current_attempt = 1
        qa_passed = False
        
        while current_attempt <= MAX_RETRIES and not qa_passed:
            logger.info(f"Sending ticket {ticket_id} to Developer agent (attempt {current_attempt}/{MAX_RETRIES})")
            update_ticket_status(ticket_id, "processing", {"current_attempt": current_attempt})
            
            # Update JIRA
            if current_attempt == 1:
                await update_jira_ticket(ticket_id, "", "Developer generating patch")
            else:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Developer generating revised patch (attempt {current_attempt}/{MAX_RETRIES})"
                )
            
            # Developer context
            developer_context = {"previousAttempts": []}
            if current_attempt > 1 and active_tickets[ticket_id].get("qa_results"):
                developer_context["previousAttempts"].append({
                    "attempt": current_attempt - 1,
                    "qaResults": active_tickets[ticket_id]["qa_results"]
                })
            
            # Call Developer
            developer_input = {
                "ticket_id": ticket_id,
                "plannerAnalysis": planner_analysis,
                "attempt": current_attempt,
                "maxAttempts": MAX_RETRIES,
                "context": developer_context
            }
            
            log_agent_input(ticket_id, "developer", developer_input)
            developer_response = await call_developer_agent(planner_analysis, current_attempt, developer_context)
            
            if developer_response:
                log_agent_output(ticket_id, "developer", developer_response)
            else:
                log_error(ticket_id, "developer", f"Developer patch generation failed on attempt {current_attempt}")
                update_ticket_status(ticket_id, "error")
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"BugFix AI: Developer patch generation failed on attempt {current_attempt}. Escalating to human review."
                )
                return
                
            update_ticket_status(ticket_id, "processing", {"developer_diffs": developer_response})
            
            # Call QA
            logger.info(f"Sending ticket {ticket_id} to QA agent (attempt {current_attempt})")
            await update_jira_ticket(ticket_id, "", f"QA testing fix (attempt {current_attempt})")
            
            qa_input = {
                "ticket_id": ticket_id,
                "diffs": developer_response["diffs"],
                "attempt": current_attempt
            }
            log_agent_input(ticket_id, "qa", qa_input)
            
            qa_response = await call_qa_agent(developer_response)
            qa_passed = process_qa_results(ticket_id, developer_response, qa_response)
            
            update_ticket_status(ticket_id, "processing", {"qa_results": qa_response})
            
            if not qa_passed and current_attempt >= MAX_RETRIES:
                update_ticket_status(ticket_id, "escalated")
                await update_jira_ticket(
                    ticket_id,
                    "Needs Review",
                    f"BugFix AI: All {MAX_RETRIES} fix attempts failed. This ticket requires human attention.",
                    {"needs_human_review": True}
                )
                return
            
            current_attempt += 1
        
        if not qa_passed:
            return
        
        # Step 5: Communicator for successful fix
        logger.info(f"Sending ticket {ticket_id} to Communicator agent")
        
        communicator_input = {
            "ticket_id": ticket_id,
            "diffs": developer_response["diffs"],
            "test_results": qa_response["test_results"],
            "commit_message": developer_response["commit_message"],
            "qa_passed": qa_passed,
            "attempts": current_attempt
        }
        log_agent_input(ticket_id, "communicator", communicator_input)
        
        communicator_response = await call_communicator_agent(
            ticket_id,
            developer_response["diffs"],
            qa_response["test_results"],
            developer_response["commit_message"]
        )
        
        if communicator_response:
            log_agent_output(ticket_id, "communicator", communicator_response)
            update_ticket_status(ticket_id, "completed", {"communicator_result": communicator_response})
            logger.info(f"Completed processing for ticket {ticket_id}")
        else:
            log_error(ticket_id, "communicator", "Failed to deploy fix")
            update_ticket_status(ticket_id, "error")
            await update_jira_ticket(
                ticket_id,
                "",
                "BugFix AI: Failed to deploy the fix. Escalating to human review."
            )
        
        # Collate all logs for this ticket
        from controller import collate_logs
        collate_logs(ticket_id)
            
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
        update_ticket_status(ticket_id, "error")
        log_error(ticket_id, "processor", f"Unhandled exception: {str(e)}")
        
        await update_jira_ticket(
            ticket_id,
            "",
            f"BugFix AI encountered an error: {str(e)}. Escalating to human review."
        )

