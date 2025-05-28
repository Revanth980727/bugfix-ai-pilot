
import os
import subprocess
import json
import tempfile
from typing import Dict, Any, List, Optional
from .agent_base import Agent, AgentStatus
from ..repo_manager import repo_manager

class EnhancedQAAgent(Agent):
    def __init__(self):
        super().__init__(name="EnhancedQAAgent")

    def run(self, developer_output: Dict[str, Any]) -> Dict[str, Any]:
        """Test the patched files"""
        self.set_status(AgentStatus.WORKING)
        
        try:
            ticket_id = developer_output.get("ticket_id", "unknown")
            patched_files = developer_output.get("patched_files", [])
            patched_code = developer_output.get("patched_code", {})
            
            if not patched_files or not patched_code:
                raise Exception("No patched files to test")
            
            # Write patched files to repository
            self._write_patched_files(patched_code)
            
            # Run tests
            test_results = self._run_tests(patched_files)
            
            # Determine overall status
            all_passed = all(result.get("status") == "pass" for result in test_results)
            
            result = {
                "ticket_id": ticket_id,
                "test_results": test_results,
                "summary": self._generate_test_summary(test_results),
                "passed": all_passed
            }
            
            self.set_status(AgentStatus.SUCCESS if all_passed else AgentStatus.ERROR)
            return result
            
        except Exception as e:
            self.log(f"Error in QA agent: {str(e)}", level="error")
            self.set_status(AgentStatus.ERROR)
            return {
                "ticket_id": developer_output.get("ticket_id", "unknown"),
                "error": str(e),
                "test_results": [],
                "passed": False
            }

    def _write_patched_files(self, patched_code: Dict[str, str]) -> None:
        """Write patched code to repository files"""
        for file_path, content in patched_code.items():
            success = repo_manager.write_file_content(file_path, content)
            if success:
                self.log(f"Successfully wrote patched content to {file_path}")
            else:
                self.log(f"Failed to write patched content to {file_path}", level="error")

    def _run_tests(self, patched_files: List[str]) -> List[Dict[str, Any]]:
        """Run tests for the patched files"""
        test_results = []
        
        # First, validate that files can be imported/parsed
        for file_path in patched_files:
            result = self._validate_file_syntax(file_path)
            test_results.append(result)
        
        # Run actual tests if available
        pytest_results = self._run_pytest_tests(patched_files)
        test_results.extend(pytest_results)
        
        return test_results

    def _validate_file_syntax(self, file_path: str) -> Dict[str, Any]:
        """Validate that a file has correct syntax"""
        import time
        start_time = time.time()
        
        try:
            content = repo_manager.get_file_content(file_path)
            if content is None:
                return {
                    "name": f"Syntax validation for {file_path}",
                    "status": "fail",
                    "duration": int((time.time() - start_time) * 1000),
                    "errorMessage": "File not found"
                }
            
            # Check syntax based on file extension
            if file_path.endswith('.py'):
                # Python syntax check
                import ast
                try:
                    ast.parse(content)
                    status = "pass"
                    error_msg = None
                except SyntaxError as e:
                    status = "fail"
                    error_msg = f"Python syntax error: {str(e)}"
            
            elif file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                # For JavaScript/TypeScript, just check basic structure
                if 'import' in content or 'export' in content or 'function' in content:
                    status = "pass"
                    error_msg = None
                else:
                    status = "fail"
                    error_msg = "File appears to be empty or invalid"
            
            else:
                # For other files, just check they're not empty
                status = "pass" if content.strip() else "fail"
                error_msg = "File is empty" if status == "fail" else None
            
            result = {
                "name": f"Syntax validation for {file_path}",
                "status": status,
                "duration": int((time.time() - start_time) * 1000)
            }
            
            if error_msg:
                result["errorMessage"] = error_msg
            
            return result
            
        except Exception as e:
            return {
                "name": f"Syntax validation for {file_path}",
                "status": "fail",
                "duration": int((time.time() - start_time) * 1000),
                "errorMessage": str(e)
            }

    def _run_pytest_tests(self, patched_files: List[str]) -> List[Dict[str, Any]]:
        """Run pytest tests in the repository"""
        try:
            # Run pytest with verbose output
            result = subprocess.run([
                "python", "-m", "pytest", "-v", "--tb=short"
            ], cwd=repo_manager.repo_path, capture_output=True, text=True, timeout=120)
            
            # Parse pytest output
            return self._parse_pytest_output(result.stdout, result.stderr, result.returncode)
            
        except subprocess.TimeoutExpired:
            return [{
                "name": "pytest execution",
                "status": "fail",
                "duration": 120000,
                "errorMessage": "Tests timed out after 120 seconds"
            }]
        except Exception as e:
            return [{
                "name": "pytest execution",
                "status": "fail",
                "duration": 0,
                "errorMessage": f"Error running tests: {str(e)}"
            }]

    def _parse_pytest_output(self, stdout: str, stderr: str, return_code: int) -> List[Dict[str, Any]]:
        """Parse pytest output to extract test results"""
        test_results = []
        
        if return_code == 0:
            # Tests passed
            test_results.append({
                "name": "pytest test suite",
                "status": "pass",
                "duration": 1000  # Placeholder duration
            })
        else:
            # Tests failed or had errors
            error_message = stderr if stderr else "Tests failed (see output)"
            test_results.append({
                "name": "pytest test suite",
                "status": "fail",
                "duration": 1000,
                "errorMessage": error_message[:500]  # Truncate long error messages
            })
        
        return test_results

    def _generate_test_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of test results"""
        total = len(test_results)
        passed = sum(1 for result in test_results if result.get("status") == "pass")
        failed = total - passed
        duration = sum(result.get("duration", 0) for result in test_results)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "duration": duration
        }
