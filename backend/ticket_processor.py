
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
from jira_utils import update_jira_ticket
from agent_utils import (
    call_planner_agent,
    call_developer_agent,
    call_qa_agent,
    call_communicator_agent
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticket-processor")

# Store active tickets
active_tickets: Dict[str, Dict[str, Any]] = {}

async def process_ticket(ticket: Dict[str, Any]):
    """Process a single ticket through the entire agent workflow"""
    ticket_id = ticket["ticket_id"]
    
    try:
        # Initialize ticket in active_tickets
        active_tickets[ticket_id] = {
            "ticket_id": ticket_id,
            "status": "processing",
            "started_at": datetime.now().isoformat(),
            "title": ticket["title"],
            "description": ticket["description"],
            "acceptance_criteria": ticket.get("acceptance_criteria", ""),
            "attachments": ticket.get("attachments", []),
            "planner_analysis": None,
            "developer_diffs": None,
            "qa_results": None,
            "communicator_result": None,
            "current_attempt": 1,
            "max_attempts": 4
        }
        
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
        
        planner_analysis = await call_planner_agent(ticket)
        if not planner_analysis:
            active_tickets[ticket_id]["status"] = "error"
            await update_jira_ticket(
                ticket_id,
                "",
                "BugFix AI: Planner analysis failed. Escalating to human review."
            )
            return
            
        active_tickets[ticket_id]["planner_analysis"] = planner_analysis
        
        # Step 2-4: Developer-QA Loop
        current_attempt = 1
        max_attempts = 4
        qa_passed = False
        
        while current_attempt <= max_attempts and not qa_passed:
            logger.info(f"Sending ticket {ticket_id} to Developer agent (attempt {current_attempt})")
            active_tickets[ticket_id]["current_attempt"] = current_attempt
            
            # Update JIRA
            if current_attempt == 1:
                await update_jira_ticket(ticket_id, "", "Developer generating patch")
            else:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Developer generating revised patch (attempt {current_attempt}/{max_attempts})"
                )
            
            # Call Developer
            developer_response = await call_developer_agent(planner_analysis, current_attempt)
            if not developer_response:
                active_tickets[ticket_id]["status"] = "error"
                await update_jira_ticket(
                    ticket_id,
                    "",
                    "BugFix AI: Developer patch generation failed. Escalating to human review."
                )
                return
                
            active_tickets[ticket_id]["developer_diffs"] = developer_response
            
            # Call QA
            logger.info(f"Sending ticket {ticket_id} to QA agent (attempt {current_attempt})")
            await update_jira_ticket(ticket_id, "", "QA testing fix")
            
            qa_response = await call_qa_agent(developer_response)
            if not qa_response:
                active_tickets[ticket_id]["status"] = "error"
                await update_jira_ticket(
                    ticket_id,
                    "",
                    "BugFix AI: QA testing failed. Escalating to human review."
                )
                return
                
            active_tickets[ticket_id]["qa_results"] = qa_response
            
            # Update JIRA with QA results
            passed_tests = sum(1 for test in qa_response["test_results"] if test["status"] == "pass")
            total_tests = len(qa_response["test_results"])
            await update_jira_ticket(
                ticket_id,
                "",
                f"QA results received: {passed_tests}/{total_tests} tests passed"
            )
            
            qa_passed = qa_response["passed"]
            if qa_passed:
                logger.info(f"QA tests passed for ticket {ticket_id} on attempt {current_attempt}")
                await update_jira_ticket(ticket_id, "", "Fix successful")
                break
            
            logger.info(f"QA tests failed for ticket {ticket_id} on attempt {current_attempt}")
            
            if current_attempt >= max_attempts:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Fix failed after {max_attempts} attempts. Escalated to human reviewer."
                )
            else:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Fix attempt {current_attempt}/{max_attempts} failed, retrying..."
                )
            
            current_attempt += 1
        
        # Step 5: Communicator
        logger.info(f"Sending ticket {ticket_id} to Communicator agent")
        communicator_response = await call_communicator_agent(
            ticket_id,
            developer_response["diffs"],
            qa_response["test_results"],
            developer_response["commit_message"]
        )
        
        if communicator_response:
            active_tickets[ticket_id]["communicator_result"] = communicator_response
            active_tickets[ticket_id]["status"] = "completed"
            logger.info(f"Completed processing for ticket {ticket_id}")
        else:
            logger.error(f"Failed to get response from Communicator for ticket {ticket_id}")
            active_tickets[ticket_id]["status"] = "error"
            await update_jira_ticket(
                ticket_id,
                "",
                "BugFix AI: Failed to deploy the fix. Escalating to human review."
            )
            
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
        active_tickets[ticket_id]["status"] = "error"
        active_tickets[ticket_id]["error"] = str(e)
        await update_jira_ticket(
            ticket_id,
            "",
            f"BugFix AI encountered an error: {str(e)}. Escalating to human review."
        )

async def cleanup_old_tickets():
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

