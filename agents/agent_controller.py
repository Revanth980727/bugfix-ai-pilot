
import os
import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from .utils.logger import Logger
from .planner_agent import PlannerAgent
from .developer_agent import DeveloperAgent
from .qa_agent import QAAgent
from .communicator_agent import CommunicatorAgent

class AgentController:
    """
    Controller class that orchestrates the execution of the bug fixing agents.
    Runs the agents in sequence: Planner -> Developer -> QA -> Communicator.
    """
    
    def __init__(self, max_retries: int = 4):
        """
        Initialize the agent controller
        
        Args:
            max_retries: Maximum number of retry attempts for generating a successful fix
        """
        self.logger = Logger("agent_controller")
        self.max_retries = max_retries
        
        # Initialize agents
        self.planner_agent = PlannerAgent()
        self.developer_agent = DeveloperAgent(max_retries=max_retries)
        self.qa_agent = QAAgent()
        self.communicator_agent = CommunicatorAgent()
        
        # Get repo path from environment
        self.repo_path = os.environ.get("REPO_PATH", "/mnt/codebase")
        
    async def process_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a JIRA ticket through the full bug fixing pipeline
        
        Args:
            ticket_data: Dictionary with ticket information with at least
                        'ticket_id', 'title', and 'description' keys
                        
        Returns:
            Dictionary with the results of the entire process
        """
        ticket_id = ticket_data.get("ticket_id", "unknown")
        self.logger.start_task(f"Processing ticket {ticket_id}")
        
        # Create result object to track progress and results
        result = {
            "ticket_id": ticket_id,
            "start_time": time.time(),
            "status": "started",
            "stages": {},
            "current_stage": "planning"
        }
        
        try:
            # Step 1: Planner Agent - Analyze the ticket and create a task plan
            self.logger.info(f"Running PlannerAgent for ticket {ticket_id}")
            result["current_stage"] = "planning"
            
            task_plan = await self._run_agent(self.planner_agent, ticket_data)
            
            # Add ticket_id to task_plan for reference
            task_plan["ticket_id"] = ticket_id
            
            # Save task_plan to result
            result["stages"]["planning"] = {
                "status": "completed",
                "output": task_plan
            }
            
            # Step 2-4: Developer-QA loop with retries
            fix_result = await self._run_fix_loop(ticket_id, task_plan)
            
            # Add fix results to overall result
            result.update(fix_result)
            
            # Final status
            result["end_time"] = time.time()
            result["duration"] = result["end_time"] - result["start_time"]
            
            self.logger.end_task(f"Processing ticket {ticket_id}", success=True)
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing ticket {ticket_id}: {str(e)}")
            
            result["status"] = "failed"
            result["error"] = str(e)
            result["end_time"] = time.time()
            result["duration"] = result["end_time"] - result["start_time"]
            
            self.logger.end_task(f"Processing ticket {ticket_id}", success=False)
            return result
            
    async def _run_fix_loop(self, ticket_id: str, task_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Run the developer-QA-communicator loop with retries"""
        result = {
            "current_stage": "development",
            "status": "in_progress",
            "stages": {},
            "fix_attempts": []
        }
        
        attempt = 1
        success = False
        
        # Context for tracking previous attempts
        context = {"previous_attempts": []}
        
        while attempt <= self.max_retries and not success:
            self.logger.info(f"Starting fix attempt {attempt}/{self.max_retries} for ticket {ticket_id}")
            
            attempt_result = {
                "attempt": attempt,
                "start_time": time.time()
            }
            
            # Step 2: Developer Agent - Generate code fix
            self.logger.info(f"Running DeveloperAgent for ticket {ticket_id} (attempt {attempt})")
            result["current_stage"] = "development"
            
            # Add attempt number to context
            context["attempt"] = attempt
            
            developer_input = {
                **task_plan,
                "context": context
            }
            
            patch_data = await self._run_agent(self.developer_agent, developer_input)
            
            # Save developer results
            attempt_result["development"] = {
                "status": "completed",
                "output": patch_data
            }
            
            # Apply patch to local repo
            patch_applied = await self._run_agent(self.developer_agent.apply_patch, patch_data)
            
            if not patch_applied:
                self.logger.error(f"Failed to apply patch for attempt {attempt}")
                attempt_result["status"] = "failed"
                attempt_result["error"] = "Failed to apply patch"
                result["fix_attempts"].append(attempt_result)
                
                # Update context for next attempt
                context["previous_attempts"].append({
                    "attempt": attempt,
                    "error": "Failed to apply patch",
                    "patch_content": patch_data.get("patch_content", "")
                })
                
                attempt += 1
                continue
            
            # Step 3: QA Agent - Run tests
            self.logger.info(f"Running QAAgent for ticket {ticket_id} (attempt {attempt})")
            result["current_stage"] = "testing"
            
            qa_input = {
                "ticket_id": ticket_id,
                "test_command": os.environ.get("TEST_COMMAND", "pytest")
            }
            
            test_results = await self._run_agent(self.qa_agent, qa_input)
            
            # Save QA results
            attempt_result["testing"] = {
                "status": "completed",
                "output": test_results
            }
            
            # Check if tests passed
            success = test_results.get("passed", False)
            
            # Log test result with enhanced information
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            result_status = "PASS" if success else "FAIL"
            
            # Include failure summary in the log if tests failed
            failure_info = ""
            if not success and "failure_summary" in test_results:
                failure_info = f" | Failure: {test_results['failure_summary'].replace(chr(10), ' ')}"
                
            log_message = f"[Ticket: {ticket_id}] Retry {attempt}/{self.max_retries} | QA Result: {result_status}{failure_info} | Timestamp: {timestamp}"
            self.logger.info(log_message)
            
            # Step 4: Communicator Agent - Update JIRA and create PR if successful
            self.logger.info(f"Running CommunicatorAgent for ticket {ticket_id} (attempt {attempt})")
            result["current_stage"] = "communication"
            
            communicator_input = {
                "ticket_id": ticket_id,
                "patch_data": patch_data,
                "test_results": test_results,
                "task_plan": task_plan,
                "attempt": attempt,
                "max_retries": self.max_retries
            }
            
            communication_result = await self._run_agent(self.communicator_agent, communicator_input)
            
            # Save communicator results
            attempt_result["communication"] = {
                "status": "completed",
                "output": communication_result
            }
            
            # Record end time for this attempt
            attempt_result["end_time"] = time.time()
            attempt_result["duration"] = attempt_result["end_time"] - attempt_result["start_time"]
            attempt_result["success"] = success
            
            # Add attempt to results
            result["fix_attempts"].append(attempt_result)
            
            # Update context for next attempt if needed
            if not success:
                context["previous_attempts"].append({
                    "attempt": attempt,
                    "patch_content": patch_data.get("patch_content", ""),
                    "qa_results": test_results
                })
            else:
                # If successful, clear the QA failure summaries
                context["previous_attempts"] = []
                
            attempt += 1
        
        # Update final status
        if success:
            result["status"] = "success"
            result["current_stage"] = "completed"
        else:
            result["status"] = "failed"
            result["error"] = f"Failed to fix after {self.max_retries} attempts"
            
        return result
        
    async def _run_agent(self, agent: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run an agent asynchronously"""
        try:
            # Use asyncio to run the agent in a thread pool
            return await asyncio.to_thread(agent.run, input_data)
        except AttributeError:
            # If the agent doesn't have a run method, try calling it directly
            return await asyncio.to_thread(agent, input_data)
