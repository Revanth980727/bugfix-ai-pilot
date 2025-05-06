
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
import json
import tempfile
import shutil
import sys

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
    command: str = "pytest"  # Default to pytest
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

def find_executable(command: str) -> str:
    """
    Find the full path to an executable command using PATH environment variable
    Returns the command name if found, or None if not found
    """
    # First check if the command already has a full path
    if os.path.isfile(command) and os.access(command, os.X_OK):
        return command
        
    # Check if command exists in PATH
    path = os.environ.get("PATH", "").split(os.pathsep)
    for directory in path:
        executable = os.path.join(directory, command)
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            return executable
            
    # Special case for pytest which might be available as a Python module
    if command == "pytest" or command == "python -m pytest":
        try:
            subprocess.run([sys.executable, "-m", "pytest", "--version"], 
                          capture_output=True, check=False)
            return f"{sys.executable} -m pytest"
        except subprocess.SubprocessError:
            pass
            
    return None

def run_tests(config: TestConfig) -> List[TestResult]:
    """Run tests and capture results"""
    results = []
    start_time = datetime.now()
    
    try:
        # Check if test command exists in the environment
        logger.info(f"Checking if test command '{config.command}' exists")
        command_parts = config.command.split()
        executable_path = find_executable(command_parts[0])
        
        if not executable_path:
            logger.error(f"Test command '{config.command}' not found in PATH")
            results.append(TestResult(
                name="test_command_verification",
                status="fail",
                duration=0,
                error_message=f"Test command '{config.command}' not found in PATH. Make sure it's installed."
            ))
            return results
            
        logger.info(f"Test command '{config.command}' found at: {executable_path}")
        
        # Prepare the full command, replacing the first part with the full path if needed
        if executable_path != command_parts[0]:
            if " " in executable_path:  # Handle case like "python -m pytest"
                exec_parts = executable_path.split()
                full_command = exec_parts + command_parts[1:]
            else:
                full_command = [executable_path] + command_parts[1:]
        else:
            full_command = command_parts
            
        logger.info(f"Running test command: {' '.join(full_command)}")
        
        # Run the test command and capture output
        process = subprocess.Popen(
            full_command,
            cwd=config.codebase_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Parse test output (this is a simplified example)
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
                error_message=stderr
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
async def test_fix(fix: DeveloperResponse):
    logger.info(f"Testing fix for ticket {fix.ticket_id} (attempt {fix.attempt})")
    
    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy codebase to temporary directory
            codebase_path = os.getenv("CODEBASE_PATH", "/app/code_repo")
            temp_codebase = os.path.join(temp_dir, "code")
            shutil.copytree(codebase_path, temp_codebase)
            
            # Apply the diffs to the temporary codebase
            apply_diffs(fix.diffs, temp_codebase)
            
            # Configure test settings
            test_config = TestConfig(
                command=os.getenv("TEST_COMMAND", "pytest"),
                codebase_path=temp_codebase
            )
            
            # Run tests
            test_results = run_tests(test_config)
            
            # Determine overall pass/fail status
            passed = all(result.status == "pass" for result in test_results)
            
            response = QAResponse(
                ticket_id=fix.ticket_id,
                passed=passed,
                test_results=test_results
            )
            
            logger.info(f"Testing completed for ticket {fix.ticket_id} (attempt {fix.attempt}): {'Passed' if passed else 'Failed'}")
            return response
            
    except Exception as e:
        logger.error(f"Error testing fix for ticket {fix.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing fix: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8003, reload=True)
