
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

    # ... keep existing code (_build_prompt and _send_gpt4_request methods)
        
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
        """Apply patches to the repository files with precise line-by-line changes"""
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
                    # If it's a new file
                    dir_path = os.path.dirname(full_path)
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                        
                    self.log(f"Creating new file: {file_path}")
                    with open(full_path, 'w') as f:
                        # For new files, use the entire diff content
                        f.write(diff)
                    
                    results["files_modified"].append(file_path)
                    results["patches_applied"] += 1
                    results["patched_code"][file_path] = diff
                    continue
                
                # For existing files, read the content
                with open(full_path, 'r') as f:
                    original_content = f.read()
                
                # Parse the diff to identify changed lines
                modified_content = self._apply_line_by_line_changes(original_content, diff)
                
                # If no changes were applied through diff format, check if it's a direct content replacement
                if modified_content == original_content:
                    # Try to detect if entire file was meant to be replaced
                    if not any(line.startswith('+') or line.startswith('-') for line in diff.splitlines()):
                        self.log(f"Replacing entire file content for {file_path}")
                        modified_content = diff
                
                # Write the modified content back
                with open(full_path, 'w') as f:
                    f.write(modified_content)
                
                # Store original and patched code
                results["patched_code"][file_path] = modified_content
                
                # Log success
                self.log(f"Successfully patched file: {file_path}")
                results["files_modified"].append(file_path)
                results["patches_applied"] += 1
                
            except Exception as e:
                error_msg = f"Failed to patch {file_path}: {str(e)}"
                self.log(error_msg)
                results["files_failed"].append({
                    "file": file_path,
                    "reason": str(e)
                })
        
        return results

    def _apply_line_by_line_changes(self, original_content: str, diff: str) -> str:
        """
        Apply diff changes line by line to preserve most of the original file
        
        Args:
            original_content: The original file content
            diff: The diff content with - and + prefixes for line changes
            
        Returns:
            Modified content with changes applied
        """
        # Check if this is a proper diff format with +/- markers
        has_diff_markers = any(line.startswith('+') or line.startswith('-') 
                              for line in diff.splitlines())
        
        if not has_diff_markers:
            # Not a diff format, return original content
            return original_content
            
        # Parse the diff to identify line changes
        original_lines = original_lines = original_content.splitlines()
        modified_lines = original_lines.copy()
        
        # Group lines into chunks for better processing
        chunks = []
        current_chunk = {"removed": [], "added": [], "context": []}
        context_lines = []
        
        # Process diff lines to extract changes
        diff_lines = diff.splitlines()
        for line in diff_lines:
            if line.startswith('+'):
                # Added line
                current_chunk["added"].append(line[1:])
            elif line.startswith('-'):
                # Removed line
                current_chunk["removed"].append(line[1:])
            else:
                # Context line - could be used for matching
                if current_chunk["removed"] or current_chunk["added"]:
                    # If we had changes in this chunk, store context and create a new chunk
                    current_chunk["context"] = context_lines
                    chunks.append(current_chunk)
                    current_chunk = {"removed": [], "added": [], "context": []}
                    context_lines = [line]
                else:
                    context_lines.append(line)
        
        # Add the last chunk if it has changes
        if current_chunk["removed"] or current_chunk["added"]:
            current_chunk["context"] = context_lines
            chunks.append(current_chunk)
        
        # Apply chunks of changes to the file
        offset = 0  # Track line offset as we add/remove lines
        
        for chunk in chunks:
            # Find the position to apply changes
            start_pos = -1
            
            # Try to find the position based on removed lines
            if chunk["removed"]:
                for i in range(len(modified_lines) - len(chunk["removed"]) + 1):
                    if i + offset >= len(modified_lines):
                        break
                    
                    # Check if this position matches the removed lines
                    matches = True
                    for j, removed_line in enumerate(chunk["removed"]):
                        if i + j + offset >= len(modified_lines):
                            matches = False
                            break
                        
                        # Strip whitespace for comparison
                        if modified_lines[i + j + offset].strip() != removed_line.strip():
                            matches = False
                            break
                    
                    if matches:
                        start_pos = i + offset
                        break
            
            # If position found, apply changes
            if start_pos != -1:
                # Remove old lines
                for _ in range(len(chunk["removed"])):
                    if start_pos < len(modified_lines):
                        modified_lines.pop(start_pos)
                
                # Add new lines at the same position
                for j, added_line in enumerate(chunk["added"]):
                    modified_lines.insert(start_pos + j, added_line)
                
                # Update offset
                offset += len(chunk["added"]) - len(chunk["removed"])
        
        return '\n'.join(modified_lines)

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

