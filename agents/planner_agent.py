
import os
import json
from typing import Dict, Any, List, Optional
import openai
from .utils.logger import Logger

class PlannerAgent:
    """
    Agent responsible for analyzing a JIRA bug ticket and creating a structured plan
    for fixing the bug, identifying relevant files and modules to modify.
    """
    
    def __init__(self):
        """Initialize the planner agent"""
        self.logger = Logger("planner_agent")
        
        # Get OpenAI API key from environment
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            self.logger.error("Missing OpenAI API key")
            raise EnvironmentError("Missing OPENAI_API_KEY environment variable")
        
        openai.api_key = self.api_key
        
    def run(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a JIRA bug ticket and identify relevant files/modules to modify
        
        Args:
            ticket_data: Dictionary containing ticket information with at least
                         'ticket_id', 'title', and 'description' keys
                         
        Returns:
            A structured task plan as a dictionary
        """
        self.logger.start_task(f"Planning for ticket {ticket_data.get('ticket_id', 'unknown')}")
        
        try:
            # Extract ticket information
            ticket_id = ticket_data.get("ticket_id", "unknown")
            title = ticket_data.get("title", "")
            description = ticket_data.get("description", "")
            
            # Create prompt for GPT-4
            prompt = self._create_planning_prompt(ticket_id, title, description)
            
            # Get analysis from GPT-4
            self.logger.info("Sending ticket to GPT-4 for analysis")
            response = self._query_gpt(prompt)
            
            # Parse and structure the response
            task_plan = self._parse_gpt_response(response)
            
            self.logger.info(f"Planning complete, identified {len(task_plan.get('files', []))} relevant files")
            self.logger.end_task(f"Planning for ticket {ticket_id}", success=True)
            
            return task_plan
            
        except Exception as e:
            self.logger.error(f"Planning failed: {str(e)}")
            self.logger.end_task(f"Planning for ticket {ticket_data.get('ticket_id', 'unknown')}", 
                                success=False)
            
            raise
            
    def _create_planning_prompt(self, ticket_id: str, title: str, description: str) -> str:
        """Create a prompt for GPT-4 to analyze the bug ticket"""
        return f"""
        You are a senior software developer analyzing a bug ticket. Your task is to create a structured plan
        for fixing this bug by identifying:
        
        1. The root cause of the issue
        2. The relevant files and modules that need to be modified
        3. A high-level approach for the fix
        
        Here's the bug ticket:
        
        Ticket ID: {ticket_id}
        Title: {title}
        
        Description:
        {description}
        
        Please provide your analysis in JSON format with the following structure:
        {{
            "root_cause": "Brief description of the root cause",
            "severity": "high/medium/low",
            "files": [
                {{
                    "path": "path/to/file.py",
                    "reason": "Why this file needs to be modified"
                }}
            ],
            "approach": "High-level description of the fix approach",
            "implementation_details": "More detailed steps for implementing the fix",
            "potential_risks": "Any potential side effects or risks of the fix"
        }}
        
        Make sure your analysis is thorough and focuses on identifying the correct files to modify.
        """
        
    def _query_gpt(self, prompt: str) -> str:
        """Query GPT-4 with the given prompt"""
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a senior software developer tasked with analyzing bug tickets and planning fixes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Error querying GPT-4: {str(e)}")
            raise
            
    def _parse_gpt_response(self, response: str) -> Dict[str, Any]:
        """Parse the GPT-4 response into a structured task plan"""
        try:
            # Extract JSON content from response
            # This handles cases where GPT might add additional text around the JSON
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_content = response[start_idx:end_idx]
                task_plan = json.loads(json_content)
                
                # Validate structure
                required_keys = ["root_cause", "files", "approach"]
                for key in required_keys:
                    if key not in task_plan:
                        self.logger.warning(f"Missing required key '{key}' in task plan")
                        task_plan[key] = "Not specified"
                        
                return task_plan
                
            else:
                self.logger.error("Failed to extract JSON from GPT response")
                return {
                    "error": "Failed to parse GPT response",
                    "raw_response": response,
                    "root_cause": "Unknown",
                    "files": [],
                    "approach": "Unable to determine"
                }
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing GPT response as JSON: {str(e)}")
            return {
                "error": f"JSON parse error: {str(e)}",
                "raw_response": response,
                "root_cause": "Unknown",
                "files": [],
                "approach": "Unable to determine"
            }
