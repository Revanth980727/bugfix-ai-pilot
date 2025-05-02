
import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import openai
from pathlib import Path
from .agent_base import Agent, AgentStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeveloperAgent(Agent):
    def __init__(self):
        super().__init__(name="DeveloperAgent")
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.log("Warning: OPENAI_API_KEY not found in environment variables")
        
        self.repo_path = os.getenv("REPO_PATH", "/app/code_repo")
        self.output_dir = os.path.join(os.path.dirname(__file__), "developer_outputs")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)

    def _build_prompt(self, ticket_id: str, summary: str, likely_files: List[str], 
                     likely_modules: List[str], likely_functions: List[str], 
                     errors: Optional[List[str]] = None,
                     code_context: Optional[Dict[str, str]] = None) -> str:
        """Build a structured prompt for GPT-4 with actual code context"""
        prompt = f"""
        I need help fixing a bug in a software project. Here's the context:
        
        Ticket ID: {ticket_id}
        
        Bug Summary: {summary}
        
        Affected Files:
        {', '.join(likely_files) if likely_files else 'No specific files mentioned'}
        
        Affected Modules/Components:
        {', '.join(likely_modules) if likely_modules else 'No specific modules mentioned'}
        
        Affected Functions/Classes:
        {', '.join(likely_functions) if likely_functions else 'No specific functions mentioned'}
        """
        
        if errors and len(errors) > 0:
            prompt += f"""
            Error Messages:
            {', '.join(errors)}
            """
        
        # Add actual code context if available
        if code_context and len(code_context) > 0:
            prompt += "\nHere is the actual code content for the affected files:\n\n"
            for file_path, content in code_context.items():
                prompt += f"File: {file_path}\n```python\n{content}\n```\n\n"
        
        prompt += """
        Instructions:
        1. Provide the minimal code fix needed to resolve this issue
        2. Include full file paths for any files that need to be modified
        3. Show exactly what code needs to be changed (in a before/after format)
        4. For each file change, explain briefly why the change fixes the issue
        
        Format your response as follows for each affected file:
        
        ---FILE: [full path to file]---
        [Brief explanation of what's being fixed]
        
        ```diff
        - [line to remove]
        + [line to add]
        ```
        
        Only include necessary changes and be as concise as possible.
        """
        
        return prompt

    def _send_gpt4_request(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Send a request to OpenAI API with retry logic"""
        # ... keep existing code
        
    def _parse_gpt_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse GPT-4 response into structured file changes with improved path handling"""
        if not response:
            return []
            
        # Pattern to extract file info blocks
        file_pattern = r'---FILE: (.*?)---(.*?)(?=---FILE:|$)'
        file_matches = re.findall(file_pattern, response, re.DOTALL)
        
        file_changes = []
        for file_path, content in file_matches:
            # Clean and normalize file path - handle placeholder paths
            file_path = file_path.strip()
            
            # Replace placeholder paths with actual project paths
            if '/path/to/' in file_path or '[full path to' in file_path:
                # Extract filename
                filename = Path(file_path).name
                # Try to find the actual file in the repo
                for root, _, files in os.walk(self.repo_path):
                    if filename in files:
                        rel_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                        self.log(f"Replaced placeholder path {file_path} with {rel_path}")
                        file_path = rel_path
                        break
            
            # Extract explanation (everything before the first code block)
            explanation_pattern = r'(.*?)```'
            explanation_match = re.search(explanation_pattern, content, re.DOTALL)
            explanation = explanation_match.group(1).strip() if explanation_match else "No explanation provided"
            
            # Extract code diff blocks
            diff_pattern = r'```(?:diff)?(.*?)```'
            diff_matches = re.findall(diff_pattern, content, re.DOTALL)
            diff = '\n'.join(diff.strip() for diff in diff_matches) if diff_matches else ""
            
            file_changes.append({
                "file_path": file_path,
                "explanation": explanation,
                "diff": diff
            })
            
        if not file_changes:
            # Fallback: try to parse without the specific file format
            self.log("No file blocks found, attempting alternate parsing")
            
            # Try to find code blocks anywhere in the response
            code_blocks = re.findall(r'```(?:.*?)\n(.*?)```', response, re.DOTALL)
            if code_blocks:
                file_changes.append({
                    "file_path": "unknown",
                    "explanation": "GPT response did not follow the expected format",
                    "diff": '\n'.join(code.strip() for code in code_blocks)
                })
        
        return file_changes

    def _apply_patch(self, file_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply patches to the repository files with improved robustness"""
        results = {
            "files_modified": [],
            "files_failed": [],
            "patches_applied": 0,
            "patched_code": {}  # Will store the actual patched code content
        }
        
        for change in file_changes:
            file_path = change["file_path"]
            diff = change["diff"]
            
            # Skip if the file path is unknown
            if file_path == "unknown":
                self.log(f"Skipping unknown file path")
                results["files_failed"].append({
                    "file": "unknown",
                    "reason": "File path could not be determined"
                })
                continue
            
            # Construct the full path
            full_path = os.path.join(self.repo_path, file_path.lstrip('/'))
            
            try:
                # Check if file exists
                if not os.path.exists(full_path):
                    dir_path = os.path.dirname(full_path)
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                    with open(full_path, 'w') as f:
                        f.write(diff)  # Create new file with content
                    
                    # Store the patched code
                    results["patched_code"][file_path] = diff
                    
                    self.log(f"Created new file: {file_path}")
                    results["files_modified"].append(file_path)
                    results["patches_applied"] += 1
                    continue
                
                # Read existing file content
                with open(full_path, 'r') as f:
                    file_content = f.read()
                
                # Apply changes based on diff pattern
                # First, try to extract explicit removal/addition patterns
                modified_content = self._apply_explicit_diff(file_content, diff)
                
                # If no changes were made, assume it's a complete file replacement
                if modified_content == file_content:
                    # Check if the diff looks like a complete file
                    if not any(line.startswith('-') or line.startswith('+') for line in diff.splitlines()):
                        modified_content = diff
                
                # Write updated content back to file
                with open(full_path, 'w') as f:
                    f.write(modified_content)
                
                # Store the patched code
                results["patched_code"][file_path] = modified_content
                
                self.log(f"Successfully updated file: {file_path}")
                results["files_modified"].append(file_path)
                results["patches_applied"] += 1
                
            except Exception as e:
                error_msg = f"Failed to apply changes to {file_path}: {str(e)}"
                self.log(error_msg)
                results["files_failed"].append({
                    "file": file_path,
                    "reason": str(e)
                })
        
        return results

    def _apply_explicit_diff(self, original_content: str, diff: str) -> str:
        """Apply explicit diff changes to the original content"""
        # ... keep existing code

    def _save_output(self, ticket_id: str, output_data: Dict[str, Any]) -> None:
        """Save the agent's output to a JSON file"""
        # ... keep existing code

    def calculate_confidence_score(self, file_changes: List[Dict[str, Any]], 
                                  expected_files: List[str], 
                                  patch_results: Dict[str, Any] = None) -> int:
        """Calculate a confidence score (0-100) for the generated patch"""
        # ... keep existing code

    def _read_code_context(self, input_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract code context from input data or read from files"""
        code_context = {}
        
        # First check if code_context is directly provided in the input
        if "code_context" in input_data and isinstance(input_data["code_context"], dict):
            return input_data["code_context"]
        
        # Otherwise, try to read affected files directly
        affected_files = input_data.get("affected_files", [])
        
        # Process affected_files to get file paths
        file_paths = []
        if isinstance(affected_files, list):
            for item in affected_files:
                if isinstance(item, str):
                    file_paths.append(item)
                elif isinstance(item, dict) and "file" in item:
                    file_paths.append(item["file"])
                    # If content is already provided, use it
                    if "content" in item:
                        code_context[item["file"]] = item["content"]
        
        # Read files that don't have content yet
        for file_path in file_paths:
            if file_path not in code_context:
                full_path = os.path.join(self.repo_path, file_path)
                try:
                    with open(full_path, 'r') as f:
                        code_context[file_path] = f.read()
                        self.log(f"Read code context for {file_path}")
                except Exception as e:
                    self.log(f"Could not read file {file_path}: {str(e)}")
        
        return code_context

    def _filter_generic_response(self, response: str) -> bool:
        """Check if the response is too generic or just explanatory text"""
        # Common patterns in generic responses
        generic_patterns = [
            r"without specific details.*challenging to provide",
            r"need more information",
            r"for demonstration purposes",
            r"hypothetical",
            r"please replace.*with the actual",
            r"please provide more details"
        ]
        
        # Check for generic patterns
        for pattern in generic_patterns:
            if re.search(pattern, response.lower()):
                self.log("Detected generic or hypothetical response")
                return True
                
        # Check for the absence of specific code changes
        if not re.search(r'```(?:diff)?.*?[-+]', response, re.DOTALL):
            self.log("No specific code changes detected in response")
            return True
            
        return False

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the developer agent to generate and apply code fixes"""
        ticket_id = input_data.get("ticket_id", "UNKNOWN")
        self.log(f"Processing ticket: {ticket_id}")
        
        # Extract data from input
        summary = input_data.get("summary", "") or input_data.get("bug_summary", "")
        
        # Handle affected_files which could be a list of strings or a list of dicts
        affected_files = input_data.get("affected_files", [])
        likely_files = []
        
        # Process affected_files to get a list of strings
        if isinstance(affected_files, list):
            for item in affected_files:
                if isinstance(item, str):
                    likely_files.append(item)
                elif isinstance(item, dict) and "file" in item:
                    # If it's a dict, extract the file path
                    likely_files.append(item["file"])
        
        likely_modules = input_data.get("affected_modules", [])
        likely_functions = input_data.get("affected_functions", [])
        errors = input_data.get("errors_identified", []) or [input_data.get("error_type", "")]
        
        # Get the code context (actual file contents)
        code_context = self._read_code_context(input_data)
        
        try:
            # Build prompt for GPT-4
            prompt = self._build_prompt(
                ticket_id=ticket_id,
                summary=summary,
                likely_files=likely_files,
                likely_modules=likely_modules,
                likely_functions=likely_functions,
                errors=errors,
                code_context=code_context
            )
            
            # Get response from GPT-4
            gpt_response = self._send_gpt4_request(prompt)
            if not gpt_response:
                raise Exception("Failed to get a valid response from GPT-4")
            
            # Check if the response is too generic or explanatory
            if self._filter_generic_response(gpt_response):
                self.log("WARNING: GPT response appears to be generic or hypothetical - might not provide a real fix")
            
            # Parse GPT-4 response to extract file changes
            file_changes = self._parse_gpt_response(gpt_response)
            if not file_changes:
                self.log("Warning: No file changes extracted from GPT response")
            
            # Apply the patches to files
            patch_results = self._apply_patch(file_changes)
            
            # Calculate confidence score
            confidence_score = self.calculate_confidence_score(file_changes, affected_files, patch_results)
            
            # Prepare output
            output = {
                "ticket_id": ticket_id,
                "files_modified": patch_results["files_modified"],
                "files_failed": patch_results["files_failed"],
                "patches_applied": patch_results["patches_applied"],
                "diff_summary": f"Applied {patch_results['patches_applied']} changes to {len(patch_results['files_modified'])} files",
                "raw_gpt_response": gpt_response,
                "confidence_score": confidence_score,
                "patched_code": patch_results.get("patched_code", {}),  # Include the actual patched code
                "timestamp": datetime.now().isoformat()
            }
            
            # Save output for debugging/auditing
            self._save_output(ticket_id, output)
            
            self.log(f"Completed processing ticket {ticket_id} with confidence score: {confidence_score}")
            return output
            
        except Exception as e:
            error_msg = f"Error during DeveloperAgent processing: {str(e)}"
            self.log(error_msg)
            return {
                "ticket_id": ticket_id,
                "error": error_msg,
                "confidence_score": 0,  # Zero confidence when error occurs
                "timestamp": datetime.now().isoformat()
            }
