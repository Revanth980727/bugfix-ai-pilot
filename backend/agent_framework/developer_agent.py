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
                      errors: Optional[List[str]] = None) -> str:
        """Build a structured prompt for GPT-4"""
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
        attempt = 0
        while attempt < max_retries:
            try:
                self.log(f"Sending request to GPT-4 (attempt {attempt + 1}/{max_retries})")
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "You are an expert software developer specializing in fixing bugs."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=3000
                )
                content = response.choices[0].message.content
                self.log("Received response from GPT-4")
                return content
            except Exception as e:
                attempt += 1
                error_msg = f"Error communicating with OpenAI API: {str(e)}"
                self.log(error_msg)
                if attempt >= max_retries:
                    self.log(f"Maximum retries ({max_retries}) reached.")
                    return None
        return None

    def _parse_gpt_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse GPT-4 response into structured file changes"""
        if not response:
            return []
            
        # Pattern to extract file info blocks
        file_pattern = r'---FILE: (.*?)---(.*?)(?=---FILE:|$)'
        file_matches = re.findall(file_pattern, response, re.DOTALL)
        
        file_changes = []
        for file_path, content in file_matches:
            # Clean file path
            file_path = file_path.strip()
            
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
        """Apply patches to the repository files"""
        results = {
            "files_modified": [],
            "files_failed": [],
            "patches_applied": 0
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
        modified_content = original_content
        lines = original_content.splitlines()
        
        # Extract removal/addition pairs
        diff_lines = diff.splitlines()
        i = 0
        
        while i < len(diff_lines):
            line = diff_lines[i].strip()
            
            # Skip context lines or diff headers
            if not line or line.startswith('diff ') or line.startswith('index ') or line.startswith('---') or line.startswith('+++'):
                i += 1
                continue
            
            # Check for removal/addition patterns
            if line.startswith('-') and i+1 < len(diff_lines) and diff_lines[i+1].startswith('+'):
                # Get the lines without the markers
                old_line = line[1:].strip()
                new_line = diff_lines[i+1][1:].strip()
                
                # Replace in the content
                modified_content = modified_content.replace(old_line, new_line)
                
                i += 2  # Skip the pair we just processed
            elif line.startswith('-'):
                # Only removal
                old_line = line[1:].strip()
                modified_content = modified_content.replace(old_line, '')
                i += 1
            elif line.startswith('+'):
                # Only addition (this is harder - we'll need context)
                # For now, we'll just append it if we can't apply it contextually
                new_line = line[1:].strip()
                if i > 0 and not diff_lines[i-1].startswith('-'):
                    modified_content += '\n' + new_line
                i += 1
            else:
                i += 1
        
        return modified_content

    def _save_output(self, ticket_id: str, output_data: Dict[str, Any]) -> None:
        """Save the agent's output to a JSON file"""
        filename = f"developer_output_{ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(output_data, f, indent=2)
            self.log(f"Output saved to {filepath}")
        except Exception as e:
            self.log(f"Error saving output to file: {str(e)}")

    def calculate_confidence_score(self, file_changes: List[Dict[str, Any]], 
                                  expected_files: List[str], 
                                  patch_results: Dict[str, Any] = None) -> int:
        """
        Calculate a confidence score (0-100) for the generated patch
        
        Args:
            file_changes: List of file changes from parse_gpt_response
            expected_files: List of files that were expected to be modified from planner analysis
            patch_results: Results of applying patch (if available)
            
        Returns:
            Integer confidence score from 0 to 100
        """
        self.log("Calculating confidence score for patch...")
        base_score = 70  # Start with a neutral score
        
        # Factor 1: Check if we modified files that were expected
        if expected_files and file_changes:
            modified_files = [change["file_path"].split("/")[-1] for change in file_changes]
            expected_file_basenames = [f.split("/")[-1] for f in expected_files]
            
            matched_files = sum(1 for f in modified_files if f in expected_file_basenames)
            unexpected_files = sum(1 for f in modified_files if f not in expected_file_basenames)
            
            # If all expected files were modified and no unexpected ones, increase confidence
            if matched_files == len(expected_file_basenames) and unexpected_files == 0:
                base_score += 10
            elif matched_files > 0:
                base_score += 5
            
            # If we modified unexpected files, reduce confidence
            if unexpected_files > 0:
                base_score -= 10 * min(unexpected_files, 3)  # Cap penalty at 3 files
                
        # Factor 2: Check patches for signs of quality
        total_lines_changed = 0
        for change in file_changes:
            diff = change.get("diff", "")
            
            # Count added/removed lines
            added_lines = len([l for l in diff.split('\n') if l.startswith('+')])
            removed_lines = len([l for l in diff.split('\n') if l.startswith('-')])
            total_lines_changed += added_lines + removed_lines
            
            # Check for potential hallucinations or issues
            if "???" in diff or "TODO" in diff or "FIXME" in diff:
                base_score -= 15
                
            # If the patch is extremely large (might be over-engineering)
            if added_lines > 100:
                base_score -= 10
                
            # If the file has a very small focused change, increase confidence
            if 1 < added_lines < 20 and 1 < removed_lines < 20:
                base_score += 5
                
        # Factor 3: Number of files changed (simpler fixes generally touch fewer files)
        num_files_changed = len(file_changes)
        if num_files_changed > 3:
            base_score -= 5 * (num_files_changed - 3)  # Penalty for many files
        
        # Factor 4: Check patch application results if available
        if patch_results:
            failed_files = len(patch_results.get("files_failed", []))
            if failed_files > 0:
                base_score -= 20  # Significant penalty for failed patches
                
        # Ensure the score is within 0-100 range
        final_score = max(0, min(100, base_score))
        
        self.log(f"Calculated confidence score: {final_score}")
        return final_score

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the developer agent to generate and apply code fixes"""
        ticket_id = input_data.get("ticket_id", "UNKNOWN")
        self.log(f"Processing ticket: {ticket_id}")
        
        # Extract data from input
        summary = input_data.get("summary", "")
        likely_files = input_data.get("affected_files", [])
        likely_modules = input_data.get("affected_modules", [])
        likely_functions = input_data.get("affected_functions", [])
        errors = input_data.get("errors_identified", [])
        
        try:
            # Build prompt for GPT-4
            prompt = self._build_prompt(
                ticket_id=ticket_id,
                summary=summary,
                likely_files=likely_files,
                likely_modules=likely_modules,
                likely_functions=likely_functions,
                errors=errors
            )
            
            # Get response from GPT-4
            gpt_response = self._send_gpt4_request(prompt)
            if not gpt_response:
                raise Exception("Failed to get a valid response from GPT-4")
            
            # Parse GPT-4 response to extract file changes
            file_changes = self._parse_gpt_response(gpt_response)
            if not file_changes:
                self.log("Warning: No file changes extracted from GPT response")
            
            # Apply the patches to files
            patch_results = self._apply_patch(file_changes)
            
            # Calculate confidence score
            confidence_score = self.calculate_confidence_score(file_changes, likely_files, patch_results)
            
            # Prepare output
            output = {
                "ticket_id": ticket_id,
                "files_modified": patch_results["files_modified"],
                "files_failed": patch_results["files_failed"],
                "patches_applied": patch_results["patches_applied"],
                "diff_summary": f"Applied {patch_results['patches_applied']} changes to {len(patch_results['files_modified'])} files",
                "raw_gpt_response": gpt_response,
                "confidence_score": confidence_score,  # Include confidence score in output
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
