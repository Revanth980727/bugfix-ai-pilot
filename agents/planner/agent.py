
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("planner-agent")

app = FastAPI(title="BugFix AI Planner Agent")

class TicketRequest(BaseModel):
    ticket_id: str
    title: str
    description: str
    repository: str

class FileInfo(BaseModel):
    path: str
    reason: Optional[str] = None

class PlannerResponse(BaseModel):
    ticket_id: str
    bug_summary: str
    affected_files: List[str]
    error_type: str
    using_fallback: bool = False
    timestamp: str = datetime.now().isoformat()

def create_planning_prompt(ticket_id: str, title: str, description: str) -> str:
    """Create a structured prompt for GPT to analyze the bug ticket"""
    return f"""
    You are a senior software developer analyzing a bug ticket. Your task is to extract key information from this ticket.
    
    Your response must be valid parsable JSON. No prose or extra text.
    
    Respond ONLY in the following strict JSON format:
    {{
        "bug_summary": "Brief one or two sentence summary of the bug",
        "affected_files": ["file1.py", "module2.js", ...],
        "error_type": "TypeError or other appropriate error classification"
    }}
    
    Here's the bug ticket:
    
    Ticket ID: {ticket_id}
    Title: {title}
    
    Description:
    {description}
    """

def extract_first_sentences(text: str, max_sentences: int = 2) -> str:
    """Extract the first 1-2 sentences from text for fallback summary"""
    # Simple sentence splitting by common endings
    sentence_endings = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_endings, text.strip())
    selected = sentences[:min(max_sentences, len(sentences))]
    return ' '.join(selected).strip()

def validate_gpt_response(response: str) -> tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validate the GPT response against our expected format
    Returns: (is_valid, parsed_json, error_message)
    """
    if not response:
        return False, None, "Empty response"
        
    # Extract JSON if wrapped in backticks or text
    json_content = response
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response, re.DOTALL)
    if json_match:
        json_content = json_match.group(1)
    else:
        # Try to find JSON object in free text
        json_match = re.search(r'({.*})', response, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
    
    try:
        data = json.loads(json_content)
        
        # Check required fields
        required_fields = ["bug_summary", "affected_files", "error_type"]
        for field in required_fields:
            if field not in data:
                return False, None, f"Missing required field: {field}"
                
        # Validate field types
        if not isinstance(data["bug_summary"], str):
            return False, None, "bug_summary must be a string"
            
        if not isinstance(data["affected_files"], list):
            return False, None, "affected_files must be a list"
            
        if not isinstance(data["error_type"], str):
            return False, None, "error_type must be a string"
            
        return True, data, "Valid JSON"
        
    except json.JSONDecodeError as e:
        return False, None, f"JSON parse error: {str(e)}"
    except Exception as e:
        return False, None, f"Validation error: {str(e)}"

def generate_fallback_output(ticket_id: str, description: str) -> Dict[str, Any]:
    """Generate fallback output when GPT response fails validation"""
    logger.warning(f"Generating fallback output for ticket {ticket_id}")
    
    # Extract first 1-2 sentences for bug summary
    bug_summary = extract_first_sentences(description)
    if len(bug_summary) > 150:  # Truncate if too long
        bug_summary = bug_summary[:147] + "..."
        
    return {
        "ticket_id": ticket_id,
        "bug_summary": bug_summary,
        "affected_files": [],
        "error_type": "Unknown",
        "using_fallback": True
    }

@app.get("/")
async def root():
    return {"message": "Planner Agent is running", "status": "healthy"}

@app.post("/analyze", response_model=PlannerResponse)
async def analyze_ticket(request: TicketRequest):
    logger.info(f"Analyzing ticket {request.ticket_id}: {request.title}")
    
    try:
        # In production, this would use OpenAI API to analyze the ticket
        # For now, we'll simulate the response
        
        # In production code, replace this with actual API call:
        # prompt = create_planning_prompt(request.ticket_id, request.title, request.description)
        # gpt_response = call_openai_api(prompt)
        # is_valid, parsed_data, error_message = validate_gpt_response(gpt_response)
        
        # For the demo, we'll always return a valid structured response
        mock_response = {
            "ticket_id": request.ticket_id,
            "bug_summary": "Login functionality fails when special characters are used in passwords because the validation function doesn't properly handle these cases.",
            "affected_files": [
                "src/components/auth/login.js",
                "src/api/userService.js",
                "src/utils/validation.js"
            ],
            "error_type": "ValidationError",
            "using_fallback": False
        }
        
        logger.info(f"Analysis completed for ticket {request.ticket_id}")
        return PlannerResponse(**mock_response)
    
    except Exception as e:
        logger.error(f"Error analyzing ticket {request.ticket_id}: {str(e)}")
        
        # Generate fallback response even in case of exception
        fallback = generate_fallback_output(request.ticket_id, request.description)
        return PlannerResponse(**fallback)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8001, reload=True)
