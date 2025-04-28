
import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
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
        Analyze a JIRA bug ticket and extract structured information
        
        Args:
            ticket_data: Dictionary containing ticket information with at least
                         'ticket_id', 'title', and 'description' keys
                         
        Returns:
            A structured analysis as a dictionary
        """
        self.logger.start_task(f"Planning for ticket {ticket_data.get('ticket_id', 'unknown')}")
        
        try:
            # Extract ticket information
            ticket_id = ticket_data.get("ticket_id", "unknown")
            title = ticket_data.get("title", "")
            description = ticket_data.get("description", "")
            
            # Create prompt for GPT
            prompt = self._create_planning_prompt(ticket_id, title, description)
            
            # Get analysis from GPT
            self.logger.info("Sending ticket to GPT for analysis")
            response = self._query_gpt(prompt)
            
            # Validate GPT response
            is_valid, parsed_data, error_message = self._validate_gpt_response(response)
            
            if is_valid and parsed_data:
                # Log success
                self.logger.info(f"[PlannerAgent] Parsed ticket {ticket_id} | Valid JSON received | Bug Summary: \"{parsed_data['bug_summary']}\"")
                
                # Structure the response
                output = {
                    "ticket_id": ticket_id,
                    "bug_summary": parsed_data["bug_summary"],
                    "affected_files": parsed_data["affected_files"],
                    "error_type": parsed_data["error_type"],
                    "using_fallback": False
                }
            else:
                # Log fallback trigger
                self.logger.warning(f"[PlannerAgent] Fallback triggered for {ticket_id} | Reason: {error_message}")
                
                # Use fallback mechanism
                output = self._generate_fallback_output(ticket_id, description)
            
            self.logger.info(f"Planning complete for ticket {ticket_id}")
            self.logger.end_task(f"Planning for ticket {ticket_id}", success=True)
            
            return output
            
        except Exception as e:
            self.logger.error(f"Planning failed: {str(e)}")
            self.logger.end_task(f"Planning for ticket {ticket_data.get('ticket_id', 'unknown')}", 
                                success=False)
            
            # Even in case of exception, return structured fallback output
            fallback_output = self._generate_fallback_output(
                ticket_data.get("ticket_id", "unknown"),
                ticket_data.get("description", "")
            )
            return fallback_output
            
    def _create_planning_prompt(self, ticket_id: str, title: str, description: str) -> str:
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
        
    def _query_gpt(self, prompt: str) -> str:
        """Query GPT with the given prompt"""
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a senior software developer tasked with analyzing bug tickets and extracting structured information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Error querying GPT: {str(e)}")
            raise
    
    def _extract_first_sentences(self, text: str, max_sentences: int = 2) -> str:
        """Extract the first 1-2 sentences from text for fallback summary"""
        # Simple sentence splitting by common endings
        sentence_endings = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_endings, text.strip())
        selected = sentences[:min(max_sentences, len(sentences))]
        return ' '.join(selected).strip()
    
    def _validate_gpt_response(self, response: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
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
            
    def _generate_fallback_output(self, ticket_id: str, description: str) -> Dict[str, Any]:
        """Generate fallback output when GPT response fails validation"""
        self.logger.warning(f"Generating fallback output for ticket {ticket_id}")
        
        # Extract first 1-2 sentences for bug summary
        bug_summary = self._extract_first_sentences(description)
        if len(bug_summary) > 150:  # Truncate if too long
            bug_summary = bug_summary[:147] + "..."
            
        return {
            "ticket_id": ticket_id,
            "bug_summary": bug_summary,
            "affected_files": [],
            "error_type": "Unknown",
            "using_fallback": True
        }
