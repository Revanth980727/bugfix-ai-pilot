
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal

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

@app.get("/")
async def root():
    return {"message": "QA Agent is running", "status": "healthy"}

@app.post("/test-fix", response_model=QAResponse)
async def test_fix(fix: DeveloperResponse):
    logger.info(f"Testing fix for ticket {fix.ticket_id} (attempt {fix.attempt})")
    
    try:
        # In a real implementation, this would run actual tests against the modified code
        # For now, we'll return mock data
        
        # Simulated test results
        if fix.attempt == 1:
            # First attempt has one failing test
            response = QAResponse(
                ticket_id=fix.ticket_id,
                passed=False,
                test_results=[
                    TestResult(
                        name="test_login_with_valid_credentials",
                        status="pass",
                        duration=156
                    ),
                    TestResult(
                        name="test_login_with_special_chars_in_password",
                        status="fail",
                        duration=124,
                        error_message="AssertionError: Expected login to succeed, but got error: 'Invalid password format'"
                    ),
                    TestResult(
                        name="test_validation_handles_special_chars",
                        status="pass",
                        duration=42
                    )
                ]
            )
        else:
            # Second attempt passes all tests
            response = QAResponse(
                ticket_id=fix.ticket_id,
                passed=True,
                test_results=[
                    TestResult(
                        name="test_login_with_valid_credentials",
                        status="pass",
                        duration=162
                    ),
                    TestResult(
                        name="test_login_with_special_chars_in_password",
                        status="pass",
                        duration=117
                    ),
                    TestResult(
                        name="test_validation_handles_special_chars",
                        status="pass",
                        duration=39
                    )
                ]
            )
        
        logger.info(f"Testing completed for ticket {fix.ticket_id} (attempt {fix.attempt}): {'Passed' if response.passed else 'Failed'}")
        return response
    
    except Exception as e:
        logger.error(f"Error testing fix for ticket {fix.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing fix: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8003, reload=True)
