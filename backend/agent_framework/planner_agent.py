
import re
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from .agent_base import Agent, AgentStatus

class PlannerAgent(Agent):
    def __init__(self):
        super().__init__(name="PlannerAgent")
        self.output_dir = os.path.join(os.path.dirname(__file__), "planner_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

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

    def _extract_first_sentences(self, text: str, max_sentences: int = 2) -> str:
        """Extract the first 1-2 sentences from text for fallback summary"""
        # Simple sentence splitting by common endings
        sentence_endings = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_endings, text.strip())
        selected = sentences[:min(max_sentences, len(sentences))]
        return ' '.join(selected).strip()

    def _validate_gpt_response(self, response: str) -> tuple[bool, Optional[Dict[str, Any]], str]:
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
        self.log(f"Generating fallback output for ticket {ticket_id}")
        
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

    def _save_output(self, ticket_id: str, output_data: Dict[str, Any]) -> None:
        """Save the analysis output to a JSON file"""
        filename = f"planner_output_{ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(output_data, f, indent=2)
        self.log(f"Analysis output saved to {filepath}")

    def _query_gpt(self, prompt: str) -> str:
        """
        Query GPT-4 with the given prompt
        This is a placeholder - in a real implementation, this would call OpenAI API
        """
        try:
            import openai
            
            # Get OpenAI API key from environment
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.log("Missing OpenAI API key")
                raise EnvironmentError("Missing OPENAI_API_KEY environment variable")
                
            openai.api_key = api_key
            
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
            self.log(f"Error querying GPT-4: {str(e)}")
            raise

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ticket and extract structured information"""
        self.log("Starting ticket analysis")
        
        ticket_id = input_data.get("ticket_id", "")
        title = input_data.get("title", "")
        description = input_data.get("description", "")
        
        try:
            # Create prompt for GPT
            prompt = self._create_planning_prompt(ticket_id, title, description)
            
            # Get analysis from GPT
            self.log(f"Sending ticket {ticket_id} to GPT for analysis")
            gpt_response = self._query_gpt(prompt)
            
            # Validate GPT response
            is_valid, parsed_data, error_message = self._validate_gpt_response(gpt_response)
            
            if is_valid and parsed_data:
                # Add additional metadata to the output
                output = {
                    "ticket_id": ticket_id,
                    "bug_summary": parsed_data["bug_summary"],
                    "affected_files": parsed_data["affected_files"],
                    "error_type": parsed_data["error_type"],
                    "using_fallback": False
                }
                
                self.log(f"[PlannerAgent] Parsed ticket {ticket_id} | Valid JSON received | Bug Summary: \"{parsed_data['bug_summary']}\"")
            else:
                # Use fallback if validation fails
                self.log(f"[PlannerAgent] Fallback triggered for {ticket_id} | Reason: {error_message}")
                output = self._generate_fallback_output(ticket_id, description)
            
            # Save output for debugging/inspection
            self._save_output(ticket_id, output)
            
            self.log("Analysis completed")
            return output
            
        except Exception as e:
            error_msg = f"Error during ticket analysis: {str(e)}"
            self.log(error_msg)
            
            # Even in case of exception, return structured output
            fallback_output = self._generate_fallback_output(ticket_id, description)
            self._save_output(ticket_id, fallback_output)
            
            return fallback_output
