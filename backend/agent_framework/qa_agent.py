
from typing import Dict, Any, List, Optional
from datetime import datetime
import subprocess
import os
import json
import logging
from .agent_base import Agent, AgentStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qa-agent")

class QAAgent(Agent):
    def __init__(self):
        super().__init__(name="QAAgent")
        self.repo_path = os.getenv("REPO_PATH", "/app/code_repo")
        
    def _run_test_command(self, command: str, timeout: int = 300) -> Dict[str, Any]:
        """Execute a test command and capture results"""
        try:
            logger.info(f"Running test command: {command}")
            process = subprocess.Popen(
                command.split(),
                cwd=self.repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=timeout)
            
            # Process test results
            test_results = []
            if process.returncode == 0:
                if stdout:
                    # Basic test result parsing - could be enhanced for specific test runners
                    test_results.append({
                        "name": "test_suite",
                        "status": "pass",
                        "duration": 0,  # Would need proper parsing from test output
                        "output": stdout
                    })
            else:
                test_results.append({
                    "name": "test_suite",
                    "status": "fail",
                    "duration": 0,
                    "output": stdout,
                    "error_message": stderr if stderr else "Test suite failed with no error output"
                })
            
            return {
                "passed": process.returncode == 0,
                "test_results": test_results,
                "exit_code": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
                "timestamp": datetime.now().isoformat()
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Test command timed out after {timeout} seconds")
            return {
                "passed": False,
                "test_results": [{
                    "name": "test_suite",
                    "status": "fail",
                    "duration": timeout * 1000,
                    "error_message": f"Test execution timed out after {timeout} seconds"
                }],
                "exit_code": -1,
                "stderr": f"Command timed out after {timeout} seconds",
                "command": command,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error running test command: {str(e)}")
            return {
                "passed": False,
                "test_results": [{
                    "name": "test_suite",
                    "status": "fail",
                    "duration": 0,
                    "error_message": str(e)
                }],
                "exit_code": -1,
                "stderr": str(e),
                "command": command,
                "timestamp": datetime.now().isoformat()
            }
    
    def _save_output(self, ticket_id: str, output: Dict[str, Any]) -> None:
        """Save QA output to file"""
        try:
            output_dir = os.path.join(self.repo_path, "qa_outputs")
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, f"qa_output_{ticket_id}.json")
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving QA output: {str(e)}")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run tests and return results"""
        ticket_id = input_data.get("ticket_id")
        if not ticket_id:
            raise ValueError("ticket_id is required")
            
        logger.info(f"Starting QA tests for ticket {ticket_id}")
        
        # Use custom test command if provided, otherwise use default
        test_command = input_data.get("test_command", "npm test")  # Default to frontend tests
        target = input_data.get("target", "")  # Optional target file/folder
        
        if target:
            test_command = f"{test_command} {target}"
            
        # Run tests and capture results
        result = self._run_test_command(test_command)
        
        # Save output for debugging
        self._save_output(ticket_id, result)
        
        # Log test completion
        status = "PASSED" if result["passed"] else "FAILED"
        logger.info(f"QA testing for ticket {ticket_id} completed: {status}")
        
        # Update agent status
        self.status = AgentStatus.SUCCESS if result["passed"] else AgentStatus.FAILED
        
        return {
            "ticket_id": ticket_id,
            "passed": result["passed"],
            "test_results": result["test_results"]
        }

