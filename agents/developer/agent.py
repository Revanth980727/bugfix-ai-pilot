
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("developer-agent")

app = FastAPI(title="BugFix AI Developer Agent")

class PlannerAnalysis(BaseModel):
    ticket_id: str
    affected_files: List[str]
    root_cause: str
    suggested_approach: str

class FileDiff(BaseModel):
    filename: str
    diff: str
    lines_added: int
    lines_removed: int

class DeveloperResponse(BaseModel):
    ticket_id: str
    diffs: List[FileDiff]
    commit_message: str
    timestamp: str = datetime.now().isoformat()
    attempt: int

@app.get("/")
async def root():
    return {"message": "Developer Agent is running", "status": "healthy"}

@app.post("/generate-fix", response_model=DeveloperResponse)
async def generate_fix(analysis: PlannerAnalysis, attempt: int = 1):
    logger.info(f"Generating fix for ticket {analysis.ticket_id} (attempt {attempt})")
    
    try:
        # In a real implementation, this would use OpenAI to generate code fixes
        # For now, we'll return mock data
        
        # Simulated code changes
        response = DeveloperResponse(
            ticket_id=analysis.ticket_id,
            diffs=[
                FileDiff(
                    filename="src/utils/validation.js",
                    diff="""@@ -15,7 +15,7 @@
 function validatePassword(password) {
-  const regex = /^[a-zA-Z0-9]{8,}$/;
+  const regex = /^[a-zA-Z0-9!@#$%^&*()_+\\-=\\[\\]{};':"\\\\|,.<>\\/?]{8,}$/;
   return regex.test(password);
 }
 """,
                    lines_added=1,
                    lines_removed=1
                ),
                FileDiff(
                    filename="src/components/auth/login.js",
                    diff="""@@ -42,6 +42,9 @@
   const handleSubmit = async (event) => {
     event.preventDefault();
     setError(null);
+    
+    // Fix: Added proper validation before submission
+    if (!validatePassword(password)) return setError("Invalid password format");
     
     try {
       await userService.login(username, password);""",
                    lines_added=3,
                    lines_removed=0
                )
            ],
            commit_message="Fix password validation to handle special characters",
            attempt=attempt
        )
        
        logger.info(f"Fix generated for ticket {analysis.ticket_id} (attempt {attempt})")
        return response
    
    except Exception as e:
        logger.error(f"Error generating fix for ticket {analysis.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating fix: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8002, reload=True)
