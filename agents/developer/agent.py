
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import openai
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("developer-agent")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="BugFix AI Developer Agent")

class PlannerAnalysis(BaseModel):
    ticket_id: str
    affected_files: List[str]
    root_cause: str
    suggested_approach: str

class TicketDetails(BaseModel):
    description: str
    reproduction_steps: Optional[str]
    acceptance_criteria: Optional[str]

class FileDiff(BaseModel):
    filename: str
    unified_diff: str  # New: unified diff format
    diff: str  # Legacy: keep for backwards compatibility
    lines_added: int
    lines_removed: int
    explanation: str
    patch_method: str = "unified_diff"  # Track how this was generated

class DeveloperResponse(BaseModel):
    ticket_id: str
    unified_diffs: List[FileDiff]  # New: prioritize unified diffs
    diffs: List[FileDiff]  # Legacy: for backwards compatibility
    patch_content: str  # Combined unified diff for all files
    commit_message: str
    timestamp: str = datetime.now().isoformat()
    attempt: int
    analysis_summary: str
    confidence_score: int = 85
    patch_mode: str = "unified_diff"

def analyze_with_gpt4(analysis: PlannerAnalysis, ticket: TicketDetails, attempt: int) -> Dict[str, Any]:
    """Use GPT-4 to analyze the bug and generate minimal diffs"""
    try:
        # Enhanced prompt for diff-first approach
        prompt = f"""
        Analyze this bug and generate MINIMAL code changes as unified diffs:

        Ticket ID: {analysis.ticket_id}
        Attempt: {attempt}

        Description:
        {ticket.description}

        Root Cause: {analysis.root_cause}
        Affected Files: {', '.join(analysis.affected_files)}
        Suggested Approach: {analysis.suggested_approach}

        IMPORTANT INSTRUCTIONS:
        1. Make MINIMAL, surgical changes only
        2. Output changes as unified diff format with 3 lines of context
        3. Focus ONLY on the specific bug fix - don't reformat existing code
        4. Keep original indentation, comments, and formatting
        5. Change only what's necessary to fix the reported issue

        For each file, provide:
        - Unified diff showing exact lines to change
        - Brief explanation of the change
        - Confidence that this fixes the root cause

        Example format:
        ```diff
        --- a/src/component.js
        +++ b/src/component.js
        @@ -10,7 +10,7 @@
           const handleClick = () => {{
             console.log("Processing click");
        -    return processData();
        +    return processData() || null;
           }};
         
           return (
        ```
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at making minimal, precise code fixes. Generate unified diffs that show only the necessary changes to fix bugs. Never rewrite entire functions unless absolutely necessary."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1  # Lower temperature for more consistent output
        )

        solution = response.choices[0].message.content
        
        # Parse the solution to extract unified diffs
        diffs = []
        combined_patch = []
        
        for file in analysis.affected_files:
            # Generate specific unified diff for each file
            file_prompt = f"""
            Generate a minimal unified diff for file {file} based on this analysis:
            {solution}
            
            Requirements:
            - Use unified diff format (--- a/path +++ b/path @@ ...)
            - Include 3 lines of context before and after changes
            - Make minimal changes only
            - Preserve existing formatting and style
            - Focus on fixing: {analysis.root_cause}
            """
            
            file_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Generate precise unified diffs. Show only necessary changes with proper context lines."},
                    {"role": "user", "content": file_prompt}
                ],
                temperature=0.1
            )
            
            unified_diff = file_response.choices[0].message.content
            
            # Extract actual diff content (remove markdown formatting if present)
            if "```diff" in unified_diff:
                unified_diff = unified_diff.split("```diff")[1].split("```")[0].strip()
            elif "```" in unified_diff:
                unified_diff = unified_diff.split("```")[1].strip()
            
            # Count lines added/removed from unified diff
            diff_lines = unified_diff.split('\n')
            lines_added = len([l for l in diff_lines if l.startswith('+')])
            lines_removed = len([l for l in diff_lines if l.startswith('-')])
            
            # Create FileDiff object
            file_diff = FileDiff(
                filename=file,
                unified_diff=unified_diff,
                diff=unified_diff,  # Legacy compatibility
                lines_added=lines_added,
                lines_removed=lines_removed,
                explanation=f"Minimal fix for {analysis.root_cause} in {file}",
                patch_method="unified_diff"
            )
            
            diffs.append(file_diff)
            
            # Add to combined patch
            combined_patch.append(unified_diff)
            combined_patch.append("")  # Empty line between files

        return {
            "diffs": diffs,
            "patch_content": "\n".join(combined_patch),
            "analysis_summary": solution
        }
        
    except Exception as e:
        logger.error(f"GPT-4 analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GPT-4 analysis failed: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Developer Agent is running", "status": "healthy"}

@app.post("/generate-fix", response_model=DeveloperResponse)
async def generate_fix(analysis: PlannerAnalysis, ticket: TicketDetails, attempt: int = 1):
    logger.info(f"Generating diff-based fix for ticket {analysis.ticket_id} (attempt {attempt})")
    
    try:
        # Generate fix using GPT-4 with diff-first approach
        solution = analyze_with_gpt4(analysis, ticket, attempt)
        
        response = DeveloperResponse(
            ticket_id=analysis.ticket_id,
            unified_diffs=solution["diffs"],
            diffs=solution["diffs"],  # Legacy compatibility
            patch_content=solution["patch_content"],
            commit_message=f"Fix {analysis.ticket_id}: {analysis.root_cause}",
            attempt=attempt,
            analysis_summary=solution["analysis_summary"],
            confidence_score=min(85 + (5 * len(analysis.affected_files)), 95),
            patch_mode="unified_diff"
        )
        
        logger.info(f"Generated unified diff fix for ticket {analysis.ticket_id} (attempt {attempt})")
        return response
    
    except Exception as e:
        logger.error(f"Error generating fix for ticket {analysis.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating fix: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8002, reload=True)
