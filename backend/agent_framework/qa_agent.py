
from typing import Dict, Any, List, Optional
from datetime import datetime
import subprocess
import os
import json
import logging
import re
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
                # Parse failure information for more detailed reporting
                failures = self._parse_test_failures(stdout, stderr)
                for failure in failures:
                    test_results.append({
                        "name": failure.get("test_name", "test_suite"),
                        "status": "fail",
                        "duration": failure.get("duration", 0),
                        "error_type": failure.get("error_type", "Error"),
                        "error_message": failure.get("error_message", stderr if stderr else "Test suite failed with no error output"),
                        "output": failure.get("output", stdout)
                    })
                
                # If no specific failures were parsed, add a generic one
                if not failures:
                    test_results.append({
                        "name": "test_suite",
                        "status": "fail",
                        "duration": 0,
                        "error_type": "UnknownError",
                        "error_message": stderr if stderr else "Test suite failed with no error output",
                        "output": stdout
                    })
            
            return {
                "passed": process.returncode == 0,
                "test_results": test_results,
                "exit_code": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "failure_summary": self._generate_failure_summary(test_results) if process.returncode != 0 else ""
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Test command timed out after {timeout} seconds")
            error_msg = f"Test execution timed out after {timeout} seconds"
            return {
                "passed": False,
                "test_results": [{
                    "name": "test_suite",
                    "status": "fail",
                    "duration": timeout * 1000,
                    "error_type": "Timeout",
                    "error_message": error_msg
                }],
                "exit_code": -1,
                "stderr": f"Command timed out after {timeout} seconds",
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "failure_summary": f"test_suite: Timeout: {error_msg}"
            }
        except Exception as e:
            logger.error(f"Error running test command: {str(e)}")
            error_msg = str(e)
            return {
                "passed": False,
                "test_results": [{
                    "name": "test_suite",
                    "status": "fail",
                    "duration": 0,
                    "error_type": "Exception",
                    "error_message": error_msg
                }],
                "exit_code": -1,
                "stderr": error_msg,
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "failure_summary": f"test_suite: Exception: {error_msg}"
            }
    
    def _parse_test_failures(self, stdout: str, stderr: str) -> List[Dict[str, Any]]:
        """Parse test output to extract specific failures"""
        failures = []
        
        # Combine stdout and stderr for parsing
        output = stdout + "\n" + stderr
        
        # Try to detect test framework by output patterns
        if "FAILED" in output and ("pytest" in output or "test_" in output):
            # Looks like pytest output
            failures = self._parse_pytest_failures(output)
        elif "FAIL:" in output and "unittest" in output:
            # Looks like unittest output
            failures = self._parse_unittest_failures(output)
        elif "fail" in output.lower() and ("jest" in output.lower() or "npm test" in output.lower()):
            # Looks like Jest/Node test output
            failures = self._parse_jest_failures(output)
        
        return failures
    
    def _parse_pytest_failures(self, output: str) -> List[Dict[str, Any]]:
        """Parse pytest failures"""
        failures = []
        # Simple regex to find pytest failures
        test_failures = re.finditer(r'(test_\w+).*FAILED', output)
        error_matches = re.finditer(r'E\s+(\w+Error|Exception):\s+(.+?)$', output, re.MULTILINE)
        
        # Collect test names and errors
        test_names = [match.group(1) for match in test_failures]
        errors = [(match.group(1), match.group(2)) for match in error_matches]
        
        # Try to match tests with their errors
        for i, test_name in enumerate(test_names):
            error_type = "AssertionError"
            error_msg = "Test failed"
            
            # Try to match with an error if available
            if i < len(errors):
                error_type, error_msg = errors[i]
            
            failures.append({
                "test_name": test_name,
                "error_type": error_type,
                "error_message": error_msg,
                "output": output
            })
        
        return failures
    
    def _parse_unittest_failures(self, output: str) -> List[Dict[str, Any]]:
        """Parse unittest failures"""
        failures = []
        # Simple regex to find unittest failures
        matches = re.finditer(r'FAIL: (\w+) \(([\w\.]+)\)', output)
        
        for match in matches:
            test_name = match.group(1)
            test_class = match.group(2)
            
            # Try to find the associated error
            error_match = re.search(rf'{test_name}.*?\n([\s\S]*?)(?=FAIL:|ERROR:|OK|$)', output)
            error_msg = error_match.group(1).strip() if error_match else "Test failed"
            
            # Try to extract error type
            error_type_match = re.search(r'(\w+Error|Exception):', error_msg)
            error_type = error_type_match.group(1) if error_type_match else "AssertionError"
            
            failures.append({
                "test_name": f"{test_class}.{test_name}",
                "error_type": error_type,
                "error_message": error_msg,
                "output": output
            })
        
        return failures
    
    def _parse_jest_failures(self, output: str) -> List[Dict[str, Any]]:
        """Parse Jest/Node test failures"""
        failures = []
        # Find Jest test failures
        test_blocks = re.split(r'●\s+', output)
        
        for block in test_blocks[1:]:  # Skip the first split which is before any match
            lines = block.strip().split('\n')
            if not lines:
                continue
                
            # First line contains the test description
            test_name = lines[0].strip()
            error_msg = "Test failed"
            error_type = "Error"
            
            # Look for error type and message
            for line in lines:
                error_match = re.search(r'(\w+Error|Error):\s+(.+)$', line)
                if error_match:
                    error_type = error_match.group(1)
                    error_msg = error_match.group(2)
                    break
            
            failures.append({
                "test_name": test_name,
                "error_type": error_type,
                "error_message": error_msg,
                "output": block
            })
        
        return failures
    
    def _generate_failure_summary(self, test_results: List[Dict[str, Any]]) -> str:
        """Generate a concise summary of test failures"""
        if not test_results:
            return "No test results available"
            
        summary_lines = []
        for test in test_results:
            if test["status"] == "fail":
                error_type = test.get("error_type", "Error")
                error_msg = test.get("error_message", "Unknown error")
                
                # Format the error message - take only the first line if it's multiline
                if isinstance(error_msg, str):
                    error_msg_first_line = error_msg.split('\n')[0]
                    if len(error_msg_first_line) > 100:
                        error_msg_first_line = error_msg_first_line[:97] + "..."
                else:
                    error_msg_first_line = str(error_msg)
                
                summary_line = f"{test['name']}: {error_type}: {error_msg_first_line}"
                summary_lines.append(summary_line)
        
        return "\n- ".join([""] + summary_lines) if summary_lines else "All tests passed"
    
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
        
        # If tests failed, log the failure summary
        if not result["passed"] and "failure_summary" in result:
            logger.info(f"Failure summary for ticket {ticket_id}:\n{result['failure_summary']}")
        
        # Update agent status
        self.status = AgentStatus.SUCCESS if result["passed"] else AgentStatus.FAILED
        
        return {
            "ticket_id": ticket_id,
            "passed": result["passed"],
            "test_results": result["test_results"],
            "failure_summary": result.get("failure_summary", "") if not result["passed"] else ""
        }
