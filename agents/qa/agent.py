from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
import json
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("qa-agent")

app = FastAPI(title="BugFix AI QA Agent")

class FileDiff(BaseModel):
    filename: str
    diff: str
    lines_added: int
    lines_removed: int

class DeveloperResponse(BaseModel):
    ticket_id: str
    diffs: List[FileDiff]
    commit_message: str
    attempt: int

class TestResult(BaseModel):
    name: str
    status: Literal["pass", "fail"]
    duration: int
    output: Optional[str] = None
    error_message: Optional[str] = None

class QAResponse(BaseModel):
    ticket_id: str
    passed: bool
    test_results: List[TestResult]
    timestamp: str = datetime.now().isoformat()

class TestConfig(BaseModel):
    command: str = "python -m pytest"  # Default to pytest as a Python module
    codebase_path: str = "/app/code_repo"
    focused_tests: Optional[List[str]] = None

def apply_diffs(diffs: List[FileDiff], base_path: str) -> None:
    """Apply code diffs to the codebase"""
    for diff in diffs:
        file_path = os.path.join(base_path, diff.filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Create or update file with the new content
        # In a real implementation, this would properly apply the git-style diff
        # For now, we'll just write the entire file content
        with open(file_path, 'w') as f:
            f.write(diff.diff)

def write_tests(test_code: Dict[str, str], codebase_path: str) -> List[str]:
    """
    Write test files to the codebase directory
    
    Args:
        test_code: Dictionary mapping filenames to test content
        codebase_path: Path to the codebase directory
        
    Returns:
        List of written test files
    """
    if not test_code:
        logger.info("No test code provided")
        return []
        
    written_files = []
    for filename, content in test_code.items():
        try:
            file_path = os.path.join(codebase_path, filename)
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w') as f:
                f.write(content)
                
            logger.info(f"Successfully wrote test file: {filename}")
            written_files.append(filename)
        except Exception as e:
            logger.error(f"Error writing test file {filename}: {str(e)}")
            
    return written_files

def run_tests(config: TestConfig) -> List[TestResult]:
    """Run tests and capture results"""
    results = []
    start_time = datetime.now()
    
    try:
        # Get current environment variables for debugging
        env = os.environ.copy()
        logger.info(f"Environment variables: PATH={env.get('PATH')}, PYTHONPATH={env.get('PYTHONPATH')}")
        
        # Check if pytest is available before attempting to run
        try:
            # Try to import pytest to make sure it's available
            import pytest
            logger.info(f"Found pytest version: {pytest.__version__}")
        except ImportError:
            # If pytest isn't available, run a pip install
            logger.warning("Pytest not found, attempting to install...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], check=True)
                logger.info("Installed pytest")
            except Exception as e:
                logger.error(f"Failed to install pytest: {str(e)}")
                return [TestResult(
                    name="test_suite",
                    status="fail",
                    duration=0,
                    error_message=f"Failed to install pytest: {str(e)}"
                )]
        
        # Always use python -m pytest - we're in a Python container
        command_parts = [sys.executable, "-m", "pytest"]
        
        # Add any test-specific arguments if they exist in the command
        if config.command != "python -m pytest" and " " in config.command:
            # Extract any arguments after the base command
            args = config.command.split(" ", 2)[2:]  # This will give us arguments after "python -m pytest"
            if args:
                command_parts.extend(args)
        
        logger.info(f"Running tests with command: {' '.join(command_parts)}")
        
        # Run the test command with environment variables properly passed
        process = subprocess.Popen(
            command_parts,
            cwd=config.codebase_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy()  # Pass current environment variables
        )
        
        stdout, stderr = process.communicate()
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log both stdout and stderr for debugging
        logger.info(f"Command stdout: {stdout}")
        if stderr:
            logger.info(f"Command stderr: {stderr}")
            
        logger.info(f"Test command exited with code {process.returncode}")
        
        # Parse test output
        if process.returncode == 0:
            results.append(TestResult(
                name="test_suite",
                status="pass",
                duration=duration,
                output=stdout
            ))
        else:
            results.append(TestResult(
                name="test_suite",
                status="fail",
                duration=duration,
                output=stdout,
                error_message=stderr or "Test failed with no error message"
            ))
            
    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        results.append(TestResult(
            name="test_suite",
            status="fail",
            duration=0,
            error_message=str(e)
        ))
    
    return results

@app.get("/")
async def root():
    return {"message": "QA Agent is running", "status": "healthy"}

@app.post("/test", response_model=QAResponse)
async def test_fix(fix: Dict[str, Any]):
    ticket_id = fix.get("ticket_id", "unknown")
    attempt = fix.get("attempt", 1)
    logger.info(f"Testing fix for ticket {ticket_id} (attempt {attempt})")
    
    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy codebase to temporary directory
            codebase_path = os.getenv("CODEBASE_PATH", "/app/code_repo")
            temp_codebase = os.path.join(temp_dir, "code")
            
            # Ensure code_repo directory exists
            if not os.path.exists(codebase_path):
                logger.warning(f"Codebase path {codebase_path} does not exist, creating it")
                os.makedirs(codebase_path, exist_ok=True)
                
            # Copy the codebase, handling empty directories
            try:
                shutil.copytree(codebase_path, temp_codebase)
            except shutil.Error as e:
                logger.warning(f"Error during copy: {str(e)}")
                # Ensure the target directory exists even if copy failed
                os.makedirs(temp_codebase, exist_ok=True)
            
            # Apply the diffs to the temporary codebase if they exist
            if "diffs" in fix and isinstance(fix["diffs"], list):
                apply_diffs(fix["diffs"], temp_codebase)
                logger.info(f"Applied {len(fix['diffs'])} diffs to the codebase")
            elif "patched_code" in fix and isinstance(fix["patched_code"], dict):
                # Alternative: Apply patched_code directly
                for file_path, content in fix["patched_code"].items():
                    full_path = os.path.join(temp_codebase, file_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w') as f:
                        f.write(content)
                logger.info(f"Applied {len(fix['patched_code'])} patched files to the codebase")
            
            # Write test files if they exist
            written_test_files = []
            if "test_code" in fix and isinstance(fix["test_code"], dict):
                written_test_files = write_tests(fix["test_code"], temp_codebase)
                logger.info(f"Wrote {len(written_test_files)} test files to the codebase")
            
            # Configure test settings - use environment variable or default to python module approach
            test_config = TestConfig(
                command=os.getenv("TEST_COMMAND", "python -m pytest"),
                codebase_path=temp_codebase
            )
            
            # Run tests
            test_results = run_tests(test_config)
            
            # Determine overall pass/fail status
            passed = all(result.status == "pass" for result in test_results)
            
            response = QAResponse(
                ticket_id=ticket_id,
                passed=passed,
                test_results=test_results
            )
            
            logger.info(f"Testing completed for ticket {ticket_id} (attempt {attempt}): {'Passed' if passed else 'Failed'}")
            return response
            
    except Exception as e:
        logger.error(f"Error testing fix for ticket {ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing fix: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8003, reload=True)
