
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
        # ... keep existing code
        
    def _send_gpt4_request(self, prompt: str, max_retries: int = 3) -> Optional[str]:
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
            if '/path/to/' in file_path or '[full path to' in file_path or '/app/' in file_path:
                # Extract filename
                filename = Path(file_path).name
                self.log(f"Detected placeholder path: {file_path}, looking for actual file with name: {filename}")
                
                # Try to find the actual file in the repo
                found = False
                for root, _, files in os.walk(self.repo_path):
                    if filename in files:
                        abs_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(abs_path, self.repo_path)
                        self.log(f"Replaced placeholder path {file_path} with {rel_path}")
                        file_path = rel_path
                        found = True
                        break
                
                if not found:
                    self.log(f"Warning: Could not find actual file for placeholder {file_path}")
                    
                    # Try using GitHub repo information from .env if available
                    repo_owner = os.getenv("GITHUB_REPO_OWNER")
                    repo_name = os.getenv("GITHUB_REPO_NAME")
                    if repo_owner and repo_name:
                        self.log(f"Using GitHub repo information: {repo_owner}/{repo_name}")
                        # Apply any other transformations as needed based on repo structure
            
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
            # ... keep existing code (Fallback parsing logic)
        
        return file_changes

    def _apply_patch(self, file_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply patches to the repository files with improved line-by-line application"""
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
                    original_content = f.read()
                
                # Apply changes based on diff pattern
                modified_content = self._apply_line_changes(original_content, diff)
                
                # If no changes were made, check if it's a complete file replacement
                if modified_content == original_content:
                    # Try applying explicit diff
                    explicit_diff_content = self._apply_explicit_diff(original_content, diff)
                    
                    # If still no changes, consider it might be a complete replacement
                    if explicit_diff_content == original_content:
                        # Check if the diff looks like a complete file (no +/- markers)
                        if not any(line.startswith('-') or line.startswith('+') for line in diff.splitlines()):
                            self.log(f"Replacing entire file content for {file_path}")
                            modified_content = diff
                
                # Write updated content back to file
                with open(full_path, 'w') as f:
                    f.write(modified_content)
                
                # Store the patched code - but only store the actual changes
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

    def _apply_line_changes(self, original_content: str, diff: str) -> str:
        """Apply changes line by line based on diff markers"""
        # If there are no diff markers, return original
        if not any(line.strip().startswith(('-', '+')) for line in diff.splitlines()):
            return original_content
            
        result_lines = []
        diff_lines = diff.splitlines()
        
        # Process the diff lines to identify changes
        removal_chunks = []
        addition_chunks = []
        current_removal = []
        current_addition = []
        
        # First, parse the diff into removal and addition chunks
        for line in diff_lines:
            stripped = line.strip()
            if stripped.startswith('-'):
                current_removal.append(stripped[1:].strip())
            elif stripped.startswith('+'):
                current_addition.append(stripped[1:].strip())
            else:
                # End of a chunk
                if current_removal or current_addition:
                    removal_chunks.append(current_removal[:])
                    addition_chunks.append(current_addition[:])
                    current_removal = []
                    current_addition = []
        
        # Add the last chunk if exists
        if current_removal or current_addition:
            removal_chunks.append(current_removal)
            addition_chunks.append(current_addition)
        
        # Apply the changes to the original content
        original_lines = original_content.splitlines()
        new_content = []
        
        # If no valid chunks found, return original
        if not removal_chunks:
            return original_content
            
        i = 0
        while i < len(original_lines):
            # Try to match a removal chunk
            matched = False
            for chunk_idx, removal_chunk in enumerate(removal_chunks):
                if removal_chunk and i + len(removal_chunk) <= len(original_lines):
                    # Check if this chunk matches at current position
                    matches = all(
                        original_lines[i+j].strip() == removal[0:len(original_lines[i+j].strip())]
                        for j, removal in enumerate(removal_chunk)
                        if j < len(removal_chunk)
                    )
                    
                    if matches:
                        # Replace with additions
                        for add_line in addition_chunks[chunk_idx]:
                            new_content.append(add_line)
                        
                        # Skip the removed lines
                        i += len(removal_chunk)
                        matched = True
                        break
            
            if not matched:
                # No match found, keep original line
                new_content.append(original_lines[i])
                i += 1
        
        return '\n'.join(new_content)

    def _apply_explicit_diff(self, original_content: str, diff: str) -> str:
        """Apply explicit diff changes to the original content"""
        # Split content into lines for easier manipulation
        original_lines = original_content.splitlines()
        result_lines = original_lines.copy()
        
        # Extract diff chunks (sections that start with - and + lines)
        chunk_pattern = r'(?:^|\n)((?:[-+][^\n]*\n)+)'
        chunks = re.findall(chunk_pattern, diff, re.MULTILINE)
        
        for chunk in chunks:
            # Extract lines to remove and add
            remove_lines = [line[1:] for line in chunk.splitlines() if line.startswith('-')]
            add_lines = [line[1:] for line in chunk.splitlines() if line.startswith('+')]
            
            # Find where to apply the changes
            if remove_lines:
                # Try to find a sequence match in the original content
                for i in range(len(result_lines) - len(remove_lines) + 1):
                    if all(result_lines[i+j].strip() == remove_line.strip() 
                           for j, remove_line in enumerate(remove_lines)):
                        # Found a match, replace these lines
                        result_lines[i:i+len(remove_lines)] = add_lines
                        break
        
        return '\n'.join(result_lines)

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
                        content = f.read()
                        code_context[file_path] = content
                        self.log(f"Read code context for {file_path}")
                except Exception as e:
                    self.log(f"Could not read file {file_path}: {str(e)}")
                    code_context[file_path] = f"ERROR: Could not read file ({str(e)})"
        
        return code_context

    def _filter_generic_response(self, response: str) -> bool:
        """Check if the response is too generic or just explanatory text"""
        # ... keep existing code

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the developer agent to generate and apply code fixes"""
        # ... keep existing code
