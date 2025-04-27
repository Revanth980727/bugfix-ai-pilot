
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticket-processor")

# Store active tickets
active_tickets: Dict[str, Dict[str, Any]] = {}

async def process_ticket(ticket: Dict[str, Any]):
    """Process a single ticket through the entire agent workflow"""
    ticket_id = ticket["ticket_id"]
    
    try:
        # Create log directory for this ticket if it doesn't exist
        ticket_log_dir = f"logs/{ticket_id}"
        os.makedirs(ticket_log_dir, exist_ok=True)
        
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
            "max_attempts": MAX_RETRIES
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
        
        # Log input to planner
        with open(f"{ticket_log_dir}/planner_input.json", 'w') as f:
            json.dump(ticket, f, indent=2)
        
        planner_analysis = await call_planner_agent(ticket)
        
        # Log output from planner
        if planner_analysis:
            with open(f"{ticket_log_dir}/planner_output.json", 'w') as f:
                json.dump(planner_analysis, f, indent=2)
        else:
            # Log error
            error_log = {
                "timestamp": datetime.now().isoformat(),
                "message": "Planner analysis failed"
            }
            with open(f"{ticket_log_dir}/planner_errors.json", 'a') as f:
                f.write(json.dumps(error_log) + "\n")
            
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
        qa_passed = False
        
        while current_attempt <= MAX_RETRIES and not qa_passed:
            logger.info(f"Sending ticket {ticket_id} to Developer agent (attempt {current_attempt}/{MAX_RETRIES})")
            active_tickets[ticket_id]["current_attempt"] = current_attempt
            
            # Update JIRA
            if current_attempt == 1:
                await update_jira_ticket(ticket_id, "", "Developer generating patch")
            else:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Developer generating revised patch (attempt {current_attempt}/{MAX_RETRIES})"
                )
            
            # On retry, include previous QA results for context
            developer_context = {
                "previousAttempts": []
            }
            
            if current_attempt > 1 and active_tickets[ticket_id].get("qa_results"):
                developer_context["previousAttempts"].append({
                    "attempt": current_attempt - 1,
                    "qaResults": active_tickets[ticket_id]["qa_results"]
                })
            
            # Log input to developer
            developer_input = {
                "ticket_id": ticket_id,
                "plannerAnalysis": planner_analysis,
                "attempt": current_attempt,
                "maxAttempts": MAX_RETRIES,
                "context": developer_context
            }
            
            with open(f"{ticket_log_dir}/developer_input_{current_attempt}.json", 'w') as f:
                json.dump(developer_input, f, indent=2)
            
            # Call Developer
            developer_response = await call_developer_agent(planner_analysis, current_attempt, developer_context)
            
            # Log output from developer
            if developer_response:
                with open(f"{ticket_log_dir}/developer_output_{current_attempt}.json", 'w') as f:
                    json.dump(developer_response, f, indent=2)
            else:
                # Log error
                error_log = {
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Developer patch generation failed on attempt {current_attempt}"
                }
                with open(f"{ticket_log_dir}/developer_errors.json", 'a') as f:
                    f.write(json.dumps(error_log) + "\n")
                
            if not developer_response:
                active_tickets[ticket_id]["status"] = "error"
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"BugFix AI: Developer patch generation failed on attempt {current_attempt}. Escalating to human review."
                )
                return
                
            active_tickets[ticket_id]["developer_diffs"] = developer_response
            
            # Call QA
            logger.info(f"Sending ticket {ticket_id} to QA agent (attempt {current_attempt})")
            await update_jira_ticket(ticket_id, "", f"QA testing fix (attempt {current_attempt})")
            
            # Log input to QA
            qa_input = {
                "ticket_id": ticket_id,
                "diffs": developer_response["diffs"],
                "attempt": current_attempt
            }
            with open(f"{ticket_log_dir}/qa_input_{current_attempt}.json", 'w') as f:
                json.dump(qa_input, f, indent=2)
            
            qa_response = await call_qa_agent(developer_response)
            
            # Log output from QA
            if qa_response:
                with open(f"{ticket_log_dir}/qa_output_{current_attempt}.json", 'w') as f:
                    json.dump(qa_response, f, indent=2)
            else:
                # Log error
                error_log = {
                    "timestamp": datetime.now().isoformat(),
                    "message": f"QA testing failed on attempt {current_attempt}"
                }
                with open(f"{ticket_log_dir}/qa_errors.json", 'a') as f:
                    f.write(json.dumps(error_log) + "\n")
            
            if not qa_response:
                active_tickets[ticket_id]["status"] = "error"
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"BugFix AI: QA testing failed on attempt {current_attempt}. Escalating to human review."
                )
                return
                
            active_tickets[ticket_id]["qa_results"] = qa_response
            
            # Update JIRA with QA results
            passed_tests = sum(1 for test in qa_response["test_results"] if test["status"] == "pass")
            total_tests = len(qa_response["test_results"])
            await update_jira_ticket(
                ticket_id,
                "",
                f"QA results for attempt {current_attempt}: {passed_tests}/{total_tests} tests passed"
            )
            
            qa_passed = qa_response["passed"]
            if qa_passed:
                logger.info(f"QA tests passed for ticket {ticket_id} on attempt {current_attempt}")
                await update_jira_ticket(ticket_id, "", "Fix successful")
                break
            
            logger.info(f"QA tests failed for ticket {ticket_id} on attempt {current_attempt}")
            
            if current_attempt >= MAX_RETRIES:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Fix failed after {MAX_RETRIES} attempts. Escalated to human reviewer."
                )
                
                # Log error for max attempts reached
                error_log = {
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Max attempts ({MAX_RETRIES}) reached without successful fix"
                }
                with open(f"{ticket_log_dir}/qa_errors.json", 'a') as f:
                    f.write(json.dumps(error_log) + "\n")
            else:
                await update_jira_ticket(
                    ticket_id,
                    "",
                    f"Fix attempt {current_attempt}/{MAX_RETRIES} failed, retrying..."
                )
            
            current_attempt += 1
        
        # If all attempts failed, escalate
        if not qa_passed:
            active_tickets[ticket_id]["status"] = "escalated"
            await update_jira_ticket(
                ticket_id,
                "Needs Review",
                f"BugFix AI: All {MAX_RETRIES} fix attempts failed. This ticket requires human attention.",
                {"needs_human_review": True}
            )
            return
        
        # Step 5: Communicator for successful fix
        logger.info(f"Sending ticket {ticket_id} to Communicator agent")
        
        # Log input to communicator
        communicator_input = {
            "ticket_id": ticket_id,
            "diffs": developer_response["diffs"],
            "test_results": qa_response["test_results"],
            "commit_message": developer_response["commit_message"],
            "qa_passed": qa_passed,
            "attempts": current_attempt
        }
        with open(f"{ticket_log_dir}/communicator_input.json", 'w') as f:
            json.dump(communicator_input, f, indent=2)
        
        communicator_response = await call_communicator_agent(
            ticket_id,
            developer_response["diffs"],
            qa_response["test_results"],
            developer_response["commit_message"]
        )
        
        # Log output from communicator
        if communicator_response:
            with open(f"{ticket_log_dir}/communicator_output.json", 'w') as f:
                json.dump(communicator_response, f, indent=2)
        else:
            # Log error
            error_log = {
                "timestamp": datetime.now().isoformat(),
                "message": "Communicator failed to deploy fix"
            }
            with open(f"{ticket_log_dir}/communicator_errors.json", 'a') as f:
                f.write(json.dumps(error_log) + "\n")
        
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
            
        # Collate all logs for this ticket
        from controller import collate_logs
        collate_logs(ticket_id)
            
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
        active_tickets[ticket_id]["status"] = "error"
        active_tickets[ticket_id]["error"] = str(e)
        
        # Log error
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "message": f"Unhandled exception: {str(e)}",
            "stacktrace": logging.traceback.format_exc()
        }
        
        try:
            with open(f"{ticket_log_dir}/processor_errors.json", 'a') as f:
                f.write(json.dumps(error_log) + "\n")
        except:
            logger.error(f"Failed to write error to log file for ticket {ticket_id}")
        
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
