
import os
import logging
import subprocess
import json
from typing import Dict, Any, Optional, List
from .agent_base import Agent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qa_agent")

class QAAgent(Agent):
    """
    Agent responsible for running tests to validate developer-generated fixes.
    Ensures that fixes pass all tests before proceeding.
    """
    
    def __init__(self):
        """Initialize the QA agent"""
        super().__init__(name="QA Agent")
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input from developer agent and run tests to validate the fix
        
        Args:
            input_data: Dictionary with data from developer agent including patch data
            
        Returns:
            Dictionary with test results
        """
        logger.info("QA Agent starting test process")
        
        # Initialize result structure
        result = {
            "passed": False,
            "test_results": [],
            "execution_time": 0,
            "error_message": None,
            "code_changes_detected": False,
            "validation_errors": [],
            "success": False
        }
        
        # Log the developer agent input
        logger.info(f"QA Agent received developer input with success={input_data.get('success', False)}")
        
        # Validate developer input
        if not self._validate_developer_input(input_data, result):
            result["error_message"] = "Invalid input from developer agent"
            logger.error(f"Developer input validation failed: {result['validation_errors']}")
            return result
            
        # Check if developer agent reported success
        if not input_data.get("success", False):
            result["error_message"] = "Developer agent reported failure"
            logger.error("Developer agent reported failure, skipping QA tests")
            return result
            
        # Verify that code changes were actually made
        logger.info("Verifying code changes")
        if not self._verify_code_changes(result):
            result["error_message"] = "No code changes detected"
            logger.error("No code changes detected in the repository")
            return result
            
        # Run tests
        logger.info("Running tests")
        success, test_output = self._run_tests(input_data.get("test_command", "pytest"))
        
        # Parse and process test results
        if success:
            logger.info("Tests passed successfully")
            result["passed"] = True
            result["test_results"] = self._parse_test_output(test_output)
            result["execution_time"] = self._calculate_execution_time(test_output)
            result["success"] = True
        else:
            logger.error("Tests failed")
            result["passed"] = False
            result["error_message"] = "Tests failed"
            result["test_results"] = self._parse_test_output(test_output)
            result["execution_time"] = self._calculate_execution_time(test_output)
            
        logger.info(f"QA Agent completed with success={result['success']}")
        return result
        
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy method for backwards compatibility.
        Delegates to run() method.
        """
        return self.run(input_data)
        
    def _validate_developer_input(self, input_data: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Validate input from developer agent
        
        Args:
            input_data: Dictionary with data from developer agent
            result: Result dictionary to update with validation errors
            
        Returns:
            Boolean indicating if input is valid
        """
        valid = True
        validation_errors = []
        
        # Check if patched_code exists and is not empty
        if "patched_code" not in input_data:
            validation_errors.append("Missing patched_code in developer output")
            valid = False
        elif not input_data["patched_code"]:
            validation_errors.append("Empty patched_code in developer output")
            valid = False
            
        # Check confidence score
        if "confidence_score" not in input_data:
            validation_errors.append("Missing confidence_score in developer output")
            valid = False
        elif input_data.get("confidence_score", 0) <= 0:
            validation_errors.append(f"Invalid confidence score: {input_data.get('confidence_score', 0)}")
            valid = False
            
        # Check patch file paths
        if "patched_files" not in input_data:
            validation_errors.append("Missing patched_files in developer output")
            valid = False
        elif not input_data.get("patched_files", []):
            validation_errors.append("Empty patched_files list in developer output")
            valid = False
            
        # Log validation results
        if validation_errors:
            result["validation_errors"] = validation_errors
            logger.warning(f"Developer input validation failed: {validation_errors}")
            try:
                logger.warning(f"Developer input: {json.dumps(input_data, indent=2)}")
            except:
                logger.warning("Could not serialize developer input for logging")
        
        return valid
        
    def _verify_code_changes(self, result: Dict[str, Any]) -> bool:
        """
        Verify that code changes were actually made using git diff
        
        Args:
            result: Result dictionary to update
            
        Returns:
            Boolean indicating if code changes were detected
        """
        try:
            # Run git diff to check for changes
            diff_process = subprocess.run(
                ["git", "diff", "--exit-code"],
                cwd=os.environ.get("REPO_PATH", "/mnt/codebase"),
                capture_output=True,
                text=True
            )
            
            # If git diff exits with code 0, there are no changes
            if diff_process.returncode == 0:
                logger.warning("No code changes detected by git diff")
                result["code_changes_detected"] = False
                return False
                
            # Changes detected
            logger.info("Code changes detected by git diff")
            result["code_changes_detected"] = True
            return True
            
        except Exception as e:
            logger.error(f"Error checking for code changes: {str(e)}")
            result["error_message"] = f"Error checking for code changes: {str(e)}"
            result["code_changes_detected"] = False
            return False
    
    def _run_tests(self, test_command: str) -> tuple:
        """
        Run tests using the specified command
        
        Args:
            test_command: Command to run tests
            
        Returns:
            Tuple of (success, output)
        """
        try:
            logger.info(f"Running test command: {test_command}")
            process = subprocess.run(
                test_command.split(),
                cwd=os.environ.get("REPO_PATH", "/mnt/codebase"),
                capture_output=True,
                text=True
            )
            
            # Check if tests passed
            success = process.returncode == 0
            logger.info(f"Test command exited with code {process.returncode}")
            
            return success, process.stdout + process.stderr
            
        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
            return False, str(e)
            
    def _parse_test_output(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse test output into structured format
        
        Args:
            output: Test output to parse
            
        Returns:
            List of test results
        """
        # Simple implementation - in a real system, you would parse the test output
        # into a structured format based on the testing framework used
        return [{"raw_output": output}]
        
    def _calculate_execution_time(self, output: str) -> float:
        """
        Calculate test execution time from output
        
        Args:
            output: Test output
            
        Returns:
            Execution time in seconds
        """
        # Simple implementation - in a real system, you would extract the actual
        # execution time from the test output
        return 1.5  # Mock execution time
