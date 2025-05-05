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
        
        # Get patch mode from environment (line-by-line, intelligent, direct)
        self.patch_mode = os.getenv("PATCH_MODE", "line-by-line")
        self.log(f"Using patch mode: {self.patch_mode}")
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)

    def _build_prompt(self, bug_title: str, bug_description: str, root_cause: str, 
                     code_context: Dict[str, str], ticket_id: str) -> str:
        """Build a prompt for GPT-4"""
        prompt = f"""
        You are a senior software developer tasked with fixing a bug. Please provide a patch for the bug described below:

        Ticket ID: {ticket_id}
        
        Bug Title: {bug_title}

        Bug Description:
        {bug_description}

        Root Cause Analysis:
        {root_cause}

        Your task is to generate code changes that will fix this bug. Please provide your solution in the form of a patch/diff format.
        
        Here are the contents of the affected files:

        """

        # Add code context
        for file_path, content in code_context.items():
            prompt += f"\n---FILE: {file_path}---\n"
            prompt += f"{content}\n"

        # Add instructions for response format
        prompt += """
        For each file that needs changes, format your response like:

        ---FILE: path/to/file---
        Brief explanation of the changes made.

        ```diff
        - line to remove
        + line to add
        ```

        Make sure to:
        1. Include proper diff markers (- for removed lines, + for added lines)
        2. Provide concise but clear explanations of changes
        3. Only include the lines that are changing plus a few lines of context
        4. Make the smallest possible changes needed to fix the bug

        If you need more context or information to properly fix the issue, please specify what additional information would help.
        """

        return prompt

    def _send_gpt4_request(self, prompt: str) -> Optional[str]:
        """Send a request to GPT-4 API and return the response"""
        if not self.api_key:
            self.log("Error: No OpenAI API key provided")
            return None
            
        try:
            self.log("Sending request to OpenAI API")
            response = self.client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": "You are a senior software developer fixing bugs."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000
            )
            
            # Check if we got a valid response
            if not response or not hasattr(response, 'choices') or not response.choices:
                self.log("Error: Invalid or empty response from OpenAI API")
                return None
                
            # Extract completion text with null safety
            completion = response.choices[0].message.content if response.choices else None
            
            if completion:
                self.log(f"Received {len(completion)} characters from OpenAI API")
            else:
                self.log("Warning: Empty completion from OpenAI API")
                
            return completion
            
        except Exception as e:
            self.log(f"Error calling OpenAI API: {str(e)}")
            return None

    def _parse_gpt_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse GPT-4 response into structured file changes with improved path handling"""
        if not response:
            self.log("Warning: Empty response received from GPT")
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
            self.log("No file changes detected in GPT response, trying fallback parsing")
            # Fallback parsing for simpler responses without proper formatting
            
            # Look for file paths and code blocks
            file_path_pattern = r'(?:in|to|file:|path:)\s*[`"]?([\w\/\.-]+\.[\w]+)[`"]?'
            code_block_pattern = r'```[\w]*\n(.*?)\n```'
            
            file_paths = re.findall(file_path_pattern, response, re.IGNORECASE)
            code_blocks = re.findall(code_block_pattern, response, re.DOTALL)
            
            # If we found at least one file path and code block, try to match them
            if file_paths and code_blocks:
                # Use the first file path and code block as a fallback
                file_changes.append({
                    "file_path": file_paths[0],
                    "explanation": "Extracted from unstructured response",
                    "diff": code_blocks[0]
                })
                self.log(f"Fallback parsing found file: {file_paths[0]}")
            else:
                self.log("Fallback parsing also failed to find file changes")
        
        return file_changes

    def _apply_patch(self, file_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply patches to the repository files with precise line-by-line changes"""
        results = {
            "files_modified": [],
            "files_failed": [],
            "patches_applied": 0,
            "patched_code": {},  # Will store the actual patched code content
            "patch_mode": self.patch_mode
        }
        
        for change in file_changes:
            file_path = change.get("file_path", "unknown")
            diff = change.get("diff", "")
            
            # Skip if the file path is unknown or diff is empty
            if file_path == "unknown":
                self.log(f"Skipping unknown file path")
                results["files_failed"].append({
                    "file": "unknown",
                    "reason": "File path could not be determined"
                })
                continue
                
            if not diff:
                self.log(f"Skipping empty diff for file {file_path}")
                results["files_failed"].append({
                    "file": file_path,
                    "reason": "Empty diff content"
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
                        # Remove diff markers before writing to a new file
                        clean_content = self._clean_diff_markers(diff)
                        f.write(clean_content)
                    
                    results["files_modified"].append(file_path)
                    results["patches_applied"] += 1
                    results["patched_code"][file_path] = clean_content
                    continue
                
                # For existing files, read the content
                with open(full_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Apply patch based on selected mode
                if self.patch_mode == "line-by-line":
                    modified_content = self._apply_line_by_line_changes(original_content, diff)
                    self.log(f"Applied line-by-line patching for {file_path}")
                elif self.patch_mode == "intelligent":
                    modified_content = self._apply_intelligent_patching(original_content, diff)
                    self.log(f"Applied intelligent patching for {file_path}")
                else:
                    # Direct mode - use clean diff content if available, otherwise keep original
                    clean_content = self._clean_diff_markers(diff)
                    if clean_content and clean_content.strip():
                        modified_content = clean_content
                        self.log(f"Applied direct content replacement for {file_path}")
                    else:
                        modified_content = original_content
                        self.log(f"Direct mode failed to extract content for {file_path}")
                
                # Skip if no changes were made
                if modified_content == original_content:
                    self.log(f"No changes were applied to {file_path}")
                    results["files_failed"].append({
                        "file": file_path,
                        "reason": "No changes could be applied"
                    })
                    continue
                    
                # Write the modified content back
                with open(full_path, 'w', encoding='utf-8') as f:
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

    def _clean_diff_markers(self, content: str) -> str:
        """Remove diff markers and metadata from content when it's a complete file"""
        # If this doesn't look like a diff with markers, return as is
        if not any(line.startswith(('+', '-', '@@ ')) for line in content.splitlines()):
            return content
        
        # If it looks like a unified diff, extract only added lines (without the + marker)
        clean_lines = []
        for line in content.splitlines():
            # Skip diff metadata lines and removal lines
            if line.startswith('@@') or line.startswith('-'):
                continue
            # Include added lines (without the + marker)
            elif line.startswith('+'):
                clean_lines.append(line[1:])
            # Include context lines (without markers)
            elif not line.startswith(('-', '+')):
                clean_lines.append(line)
        
        return '\n'.join(clean_lines)

    def _apply_line_by_line_changes(self, original_content: str, diff: str) -> str:
        """
        Apply diff changes line by line to preserve most of the original file
        
        Args:
            original_content: The original file content
            diff: The diff content with - and + prefixes for line changes
            
        Returns:
            Modified content with changes applied
        """
        self.log("Applying changes using line-by-line patching strategy")
        
        # Check if this is a proper diff format with +/- markers
        has_diff_markers = any(line.startswith('+') or line.startswith('-') 
                              for line in diff.splitlines())
        
        if not has_diff_markers:
            self.log("No diff markers found, returning original content")
            # If debug mode is enabled, log details
            if os.getenv("DEBUG_MODE", "False").lower() == "true":
                self.log(f"Diff content: {diff[:500]}...")  # Log part of the diff for debugging
            
            return original_content
            
        # Parse the diff to identify line changes
        original_lines = original_content.splitlines()
        result_lines = original_lines.copy()
        
        # Track specific added and removed lines precisely
        lines_to_remove = []  # List of (line_number, content) tuples
        lines_to_add = []     # List of (insert_position, content) tuples
        
        # Process diff lines to extract changes
        diff_lines = diff.splitlines()
        line_idx = 0  # Pointer to the current line in original content
        
        # Find chunks with hunk headers
        hunk_pattern = r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@'
        current_hunk = None
        
        # Check if diff has hunk headers (standard diff format)
        has_hunk_headers = any(re.match(hunk_pattern, line) for line in diff_lines)
        
        if has_hunk_headers:
            # Process standard diff format with hunk headers
            for diff_line in diff_lines:
                # Check for hunk header
                hunk_match = re.match(hunk_pattern, diff_line)
                if hunk_match:
                    # Start of a new hunk
                    old_start = int(hunk_match.group(1))
                    line_idx = old_start - 1  # Adjust for 0-indexing
                    continue
                
                # Process line changes
                if diff_line.startswith('-'):
                    # Line to remove
                    if line_idx < len(result_lines):
                        lines_to_remove.append((line_idx, diff_line[1:]))
                        line_idx += 1
                
                elif diff_line.startswith('+'):
                    # Line to add
                    lines_to_add.append((line_idx, diff_line[1:]))
                
                else:
                    # Context line, just advance
                    if line_idx < len(result_lines):
                        line_idx += 1
        else:
            # Handle simpler diff format (just +/- lines without hunk headers)
            # Find removals first, track them with their content for matching
            for diff_line in diff_lines:
                if diff_line.startswith('-'):
                    line_content = diff_line[1:]
                    
                    # Try to find this line in the original content
                    found = False
                    for i, orig_line in enumerate(original_lines):
                        if orig_line.strip() == line_content.strip():
                            lines_to_remove.append((i, line_content))
                            found = True
                            break
                            
                    if not found:
                        self.log(f"Warning: Could not find line to remove: '{line_content[:40]}...'")
            
            # Now process additions and try to pair them with removals
            for i, diff_line in enumerate(diff_lines):
                if diff_line.startswith('+'):
                    line_content = diff_line[1:]
                    
                    # Try to pair with previous removal
                    insert_pos = 0
                    if i > 0 and diff_lines[i-1].startswith('-'):
                        removal_content = diff_lines[i-1][1:]
                        
                        # Find matching removal position
                        for pos, content in lines_to_remove:
                            if content.strip() == removal_content.strip():
                                insert_pos = pos
                                break
                    
                    lines_to_add.append((insert_pos, line_content))
        
        # Sort lines to remove in reverse order to avoid index shifting
        lines_to_remove.sort(reverse=True)
        
        # Apply removals
        for line_num, _ in lines_to_remove:
            if 0 <= line_num < len(result_lines):
                del result_lines[line_num]
                
        # Sort additions by position
        lines_to_add.sort()
        
        # Apply additions with appropriate index adjustments
        offset = 0
        for orig_pos, content in lines_to_add:
            adjusted_pos = max(0, min(orig_pos + offset, len(result_lines)))
            result_lines.insert(adjusted_pos, content)
            offset += 1
        
        # If the diff didn't change anything, log a warning
        if result_lines == original_lines:
            self.log("Line-by-line patching did not change the file content")
            
            # Try a fallback approach - extract just the clean content from the diff
            clean_content = self._clean_diff_markers(diff)
            if clean_content and clean_content.strip() and clean_content != original_content:
                self.log("Using fallback clean content extraction")
                return clean_content
        
        return '\n'.join(result_lines)
        
    def _apply_intelligent_patching(self, original_content: str, diff: str) -> str:
        """
        Apply intelligent patching that uses multiple strategies based on diff content
        
        Args:
            original_content: The original file content
            diff: The diff content
            
        Returns:
            Modified content with changes applied
        """
        self.log("Applying changes using intelligent patching strategy")
        
        # First try standard line-by-line patching
        modified_content = self._apply_line_by_line_changes(original_content, diff)
        
        # If no changes were applied, check if we have a complete file replacement
        if modified_content == original_content:
            # Clean the diff and check if it looks like a complete file
            clean_content = self._clean_diff_markers(diff)
            
            # Heuristic: If the clean content has imports or class/function definitions, 
            # and is reasonably long, it might be a full file replacement
            looks_like_full_file = False
            if clean_content:
                lines = clean_content.splitlines()
                if len(lines) > 10:  # Reasonably sized file
                    code_markers = ['import ', 'class ', 'def ', 'function ', 'const ', 'let ', 'var ']
                    if any(marker in line for line in lines[:20] for marker in code_markers):
                        looks_like_full_file = True
                        
            if looks_like_full_file:
                self.log("Intelligent patching: Detected full file replacement")
                return clean_content
        
        return modified_content

    def _save_output(self, ticket_id: str, output_data: Dict[str, Any]) -> None:
        """Save the agent's output to a JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(self.output_dir, f"developer_output_{ticket_id}_{timestamp}.json")
        
        try:
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
                
            self.log(f"Saved developer output to {output_file}")
        except Exception as e:
            self.log(f"Error saving output to file: {str(e)}")

    def calculate_confidence_score(self, file_changes: List[Dict[str, Any]], 
                                  expected_files: List[str], 
                                  patch_results: Dict[str, Any] = None) -> int:
        """Calculate a confidence score (0-100) for the generated patch"""
        # Base score
        score = 50
        
        # No changes found
        if not file_changes:
            return 0
            
        # Check if any expected files were modified
        if expected_files:
            modified_files = patch_results.get("files_modified", []) if patch_results else []
            expected_file_matches = sum(1 for file in modified_files if any(expected in file for expected in expected_files))
            
            if expected_file_matches > 0:
                score += 15
                self.log(f"Found {expected_file_matches} expected files in patch (+15)")
            else:
                score -= 10
                self.log("No expected files were found in patch (-10)")
        
        # Check diff quality
        for change in file_changes:
            diff = change.get("diff", "")
            
            # Minimal or empty diffs
            if not diff or len(diff.strip().split("\n")) < 2:
                score -= 15
                self.log(f"Minimal or empty diff for {change.get('file_path', 'unknown')} (-15)")
                continue
                
            # Realistic diff with proper changes
            if any(line.startswith('+') or line.startswith('-') for line in diff.splitlines()):
                score += 10
                self.log(f"Found proper code changes in diff for {change.get('file_path', 'unknown')} (+10)")
        
        # Check for patch application success
        if patch_results:
            patches_applied = patch_results.get("patches_applied", 0)
            files_failed = len(patch_results.get("files_failed", []))
            
            if patches_applied > 0:
                score += 15
                self.log(f"{patches_applied} patches applied successfully (+15)")
            
            if files_failed > 0:
                score -= 10 * files_failed
                self.log(f"{files_failed} patches failed to apply (-{10 * files_failed})")
        
        # Constrain score to 0-100 range
        score = max(0, min(100, score))
        self.log(f"Final confidence score: {score}")
        
        return score

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
        if not response:
            return True
            
        # Check for indicators of generic response
        generic_phrases = [
            "need more context", 
            "need more information",
            "cannot provide a specific solution",
            "without more details",
            "please provide more"
        ]
        
        # If any generic phrases are found and no code blocks
        has_generic_phrase = any(phrase in response.lower() for phrase in generic_phrases)
        has_code_block = "```" in response
        
        if has_generic_phrase and not has_code_block:
            self.log("Response appears to be generic explanation without code")
            return True
            
        return False

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the developer agent to generate and apply code fixes"""
        try:
            # Initialize with safe defaults
            ticket_id = input_data.get("ticket_id", "unknown") if input_data else "unknown"
            self.log(f"Starting developer agent for ticket {ticket_id}")
            
            # Handle None input_data
            if input_data is None:
                self.log("Error: input_data is None")
                return {
                    "ticket_id": ticket_id,
                    "error": "No input data provided",
                    "confidence_score": 0,
                    "patch_mode": self.patch_mode,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Read code context with null safety
            code_context = self._read_code_context(input_data)
            
            # Extract bug details from input data with safe defaults
            bug_title = input_data.get("title", "Unknown bug")
            bug_description = input_data.get("description", "No description provided")
            root_cause = input_data.get("root_cause", "Unknown")
            expected_files = []
            
            # Try to extract affected files from multiple possible formats with null safety
            if "affected_files" in input_data:
                affected_files = input_data["affected_files"]
                if isinstance(affected_files, list):
                    for item in affected_files:
                        if isinstance(item, str):
                            expected_files.append(item)
                        elif isinstance(item, dict) and "file" in item:
                            expected_files.append(item["file"])
            
            # Build prompt for GPT
            prompt = self._build_prompt(
                bug_title=bug_title,
                bug_description=bug_description,
                root_cause=root_cause,
                code_context=code_context,
                ticket_id=ticket_id
            )
            
            # Log the prompt for debugging
            prompt_file = os.path.join(self.output_dir, f"developer_prompt_{ticket_id}.txt")
            with open(prompt_file, 'w') as f:
                f.write(prompt)
            self.log(f"Saved prompt to {prompt_file}")
            
            # Send prompt to GPT-4 with null safety
            self.log(f"Sending prompt to GPT-4 for ticket {ticket_id}")
            response = self._send_gpt4_request(prompt)
            
            # Save raw response for debugging if not None
            if response:
                raw_response_file = os.path.join(self.output_dir, f"developer_raw_response_{ticket_id}.txt")
                with open(raw_response_file, 'w') as f:
                    f.write(response)
                self.log(f"Saved raw response to {raw_response_file}")
            else:
                self.log("Warning: Empty response received from GPT-4")
                return {
                    "ticket_id": ticket_id,
                    "error": "Empty response received from GPT-4",
                    "confidence_score": 0,
                    "patch_mode": self.patch_mode,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Check if response is too generic
            if self._filter_generic_response(response):
                self.log("Response filtered as too generic")
                return {
                    "ticket_id": ticket_id,
                    "error": "Developer agent returned a generic response",
                    "confidence_score": 0,
                    "patch_mode": self.patch_mode,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Parse response into file changes with null safety
            file_changes = self._parse_gpt_response(response)
            if not file_changes:
                self.log("No file changes extracted from GPT response")
                return {
                    "ticket_id": ticket_id,
                    "error": "No file changes could be extracted from LLM response",
                    "confidence_score": 0,
                    "patch_mode": self.patch_mode,
                    "timestamp": datetime.now().isoformat()
                }
                
            self.log(f"Extracted {len(file_changes)} file changes from GPT response")
            
            # Apply patches to files with null safety
            patch_results = self._apply_patch(file_changes)
            files_modified = patch_results.get("files_modified", [])
            patches_applied = patch_results.get("patches_applied", 0)
            
            self.log(f"Applied {patches_applied} changes to {len(files_modified)} files using {self.patch_mode} mode")
            
            # Calculate confidence score with null safety
            confidence_score = self.calculate_confidence_score(
                file_changes, expected_files, patch_results)
            
            # Prepare result
            result = {
                "ticket_id": ticket_id,
                "files_modified": files_modified,
                "files_failed": patch_results.get("files_failed", []),
                "patches_applied": patches_applied,
                "diff_summary": f"Applied {patches_applied} changes to {len(files_modified)} files",
                "raw_gpt_response": response,
                "confidence_score": confidence_score,
                "patch_mode": self.patch_mode,
                "patched_code": patch_results.get("patched_code", {}),
                "timestamp": datetime.now().isoformat()
            }
            
            # Save output data
            self._save_output(ticket_id, result)
            return result
                
        except Exception as e:
            error_message = f"Error during DeveloperAgent processing: {str(e)}"
            self.log(f"Error: {error_message}")
            import traceback
            self.log(traceback.format_exc())
            
            return {
                "ticket_id": input_data.get("ticket_id", "unknown") if input_data else "unknown",
                "error": error_message,
                "confidence_score": 0,
                "patch_mode": self.patch_mode,
                "timestamp": datetime.now().isoformat()
            }
