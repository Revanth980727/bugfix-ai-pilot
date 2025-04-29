import logging
import asyncio
import os
import json
from datetime import datetime
from typing import Dict, Any, List
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

# Get retry delay from environment or default to 5 seconds
RETRY_DELAY_SECONDS = int(os.environ.get('RETRY_DELAY_SECONDS', '5'))

async def process_ticket(ticket: Dict[str, Any]):
    """Process a single ticket through the enhanced agent workflow"""
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
        
        # Step 1: Enhanced Planner Analysis
        logger.info(f"Sending ticket {ticket_id} to enhanced Planner agent")
        await update_jira_ticket(ticket_id, "", "Planner analyzing bug")
        
        # Prepare enhanced input with additional ticket fields
        enhanced_ticket = ticket.copy()
        
        # Try to fetch additional fields if not already in ticket
        if 'jira_id' in ticket and ('labels' not in ticket or 'attachments' not in ticket):
            try:
                # This would fetch additional ticket data from JIRA in a real implementation
                # For now, let's just log that we would do this
                logger.info(f"Would fetch additional JIRA fields for ticket {ticket_id}")
                
                # Placeholder for fetched data
                # enhanced_ticket['labels'] = ['bug', 'critical', 'backend']
                # enhanced_ticket['attachments'] = ['screenshot.png', 'logs.txt']
            except Exception as e:
                logger.warning(f"Could not fetch additional ticket data: {str(e)}")
        
        log_agent_input(ticket_id, "planner", enhanced_ticket)
        planner_analysis = await call_planner_agent(enhanced_ticket)
        
        if planner_analysis:
            log_agent_output(ticket_id, "planner", planner_analysis)
            
            # Log information about file validation results
            if 'affected_files' in planner_analysis and isinstance(planner_analysis['affected_files'], list):
                valid_files = 0
                invalid_files = 0
                
                for file_item in planner_analysis['affected_files']:
                    if isinstance(file_item, dict) and 'valid' in file_item:
                        if file_item['valid']:
                            valid_files += 1
                        else:
                            invalid_files += 1
                
                if valid_files > 0 or invalid_files > 0:
                    logger.info(f"Planner identified {valid_files} valid files and {invalid_files} invalid files")
            
            # Check if fallback was used
            if planner_analysis.get('using_fallback'):
                logger.warning(f"Planner used fallback mechanism for ticket {ticket_id}")
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
        retry_history = []  # Track retry history with QA results
        
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
            
            # Developer context with QA feedback from previous attempts
            developer_context = {"previousAttempts": retry_history}
            
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
            
            # Log retry status with improved format including failure summary
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            result_status = "PASS" if qa_passed else "FAIL"
            
            # Include failure summary in logs when tests fail
            failure_info = ""
            if not qa_passed and "failure_summary" in qa_response:
                failure_info = f" | Failure: {qa_response['failure_summary']}"
            
            log_message = f"[Ticket: {ticket_id}] Retry {current_attempt}/{MAX_RETRIES} | QA Result: {result_status}{failure_info} | {timestamp}"
            logger.info(log_message)
            
            # Store results for future retries
            retry_entry = {
                "attempt": current_attempt,
                "patch_content": developer_response.get("diffs", []),
                "qa_results": qa_response
            }
            retry_history.append(retry_entry)
            
            if not qa_passed and current_attempt >= MAX_RETRIES:
                # Max retries reached, escalate to human
                update_ticket_status(ticket_id, "escalated", {"escalated": True})
                
                # Include failure summary in escalation note
                failure_summary = qa_response.get("failure_summary", "Unknown error")
                await update_jira_ticket(
                    ticket_id,
                    "Needs Review",
                    f"BugFix AI: All {MAX_RETRIES} fix attempts failed. Last failure: {failure_summary}. This ticket requires human attention.",
                    {"needs_human_review": True}
                )
                
                # Call communicator for escalation
                communicator_input = {
                    "ticket_id": ticket_id,
                    "test_passed": False,
                    "escalated": True,
                    "retry_count": current_attempt,
                    "max_retries": MAX_RETRIES,
                    "failure_summary": failure_summary
                }
                log_agent_input(ticket_id, "communicator_escalation", communicator_input)
                
                communicator_response = await call_communicator_agent(
                    ticket_id,
                    [],
                    qa_response["test_results"],
                    f"Failed after {MAX_RETRIES} attempts: {failure_summary}",
                    escalated=True
                )
                
                if communicator_response:
                    log_agent_output(ticket_id, "communicator_escalation", communicator_response)
                
                return
            
            if not qa_passed:
                # Wait before trying again
                logger.info(f"Waiting {RETRY_DELAY_SECONDS} seconds before next retry")
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                # Clear retry history on success
                retry_history = []
            
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
            "attempts": current_attempt - 1  # -1 because we increment at end of loop
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
