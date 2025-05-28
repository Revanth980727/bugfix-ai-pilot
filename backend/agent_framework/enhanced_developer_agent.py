
import os
import json
from typing import Dict, Any, List, Optional
from .agent_base import Agent, AgentStatus
from ..repo_manager import repo_manager

class EnhancedDeveloperAgent(Agent):
    def __init__(self):
        super().__init__(name="EnhancedDeveloperAgent")

    def run(self, planner_output: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code fixes based on planner analysis"""
        self.set_status(AgentStatus.WORKING)
        
        try:
            ticket_id = planner_output.get("ticket_id", "unknown")
            affected_files = planner_output.get("affected_files", [])
            bug_summary = planner_output.get("bug_summary", "")
            error_type = planner_output.get("error_type", "")
            
            # Filter to only valid files
            valid_files = [
                f["file"] for f in affected_files 
                if isinstance(f, dict) and f.get("valid", True)
            ]
            
            if not valid_files:
                raise Exception("No valid files to process")
            
            # Read original file contents
            file_contents = {}
            for file_path in valid_files:
                content = repo_manager.get_file_content(file_path)
                if content is not None:
                    file_contents[file_path] = content
                else:
                    self.log(f"Could not read file: {file_path}")
            
            if not file_contents:
                raise Exception("Could not read any of the affected files")
            
            # Generate patches using GPT
            patches = self._generate_patches_with_gpt(
                ticket_id, bug_summary, error_type, file_contents
            )
            
            # Apply patches to get final content
            patched_files = {}
            for file_path, patch_info in patches.items():
                if patch_info.get("patched_content"):
                    patched_files[file_path] = patch_info["patched_content"]
            
            if not patched_files:
                raise Exception("No patches were successfully generated")
            
            result = {
                "ticket_id": ticket_id,
                "patched_files": list(patched_files.keys()),
                "patched_code": patched_files,
                "diffs": self._generate_diffs(file_contents, patched_files),
                "confidence_score": 85,
                "patch_mode": "unified_diff"
            }
            
            self.set_status(AgentStatus.SUCCESS)
            return result
            
        except Exception as e:
            self.log(f"Error in developer agent: {str(e)}", level="error")
            self.set_status(AgentStatus.ERROR)
            return {
                "ticket_id": planner_output.get("ticket_id", "unknown"),
                "error": str(e),
                "patched_files": [],
                "patched_code": {}
            }

    def _generate_patches_with_gpt(self, ticket_id: str, bug_summary: str, 
                                  error_type: str, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """Generate patches for files using GPT"""
        from ..openai_client import OpenAIClient
        
        patches = {}
        
        for file_path, content in file_contents.items():
            try:
                prompt = f"""
                You are fixing a bug in a code file. Generate the complete fixed version of the file.
                
                Bug Summary: {bug_summary}
                Error Type: {error_type}
                File: {file_path}
                
                Current file content:
                ```
                {content}
                ```
                
                Provide ONLY the complete fixed file content. Do not include explanations or markdown.
                """
                
                client = OpenAIClient()
                patched_content = client.get_completion(prompt)
                
                # Clean up the response
                patched_content = self._clean_gpt_response(patched_content)
                
                patches[file_path] = {
                    "patched_content": patched_content,
                    "original_content": content
                }
                
                self.log(f"Generated patch for {file_path}")
                
            except Exception as e:
                self.log(f"Error generating patch for {file_path}: {str(e)}")
        
        return patches

    def _clean_gpt_response(self, response: str) -> str:
        """Clean GPT response to extract just the code"""
        # Remove markdown code blocks if present
        if "```" in response:
            # Extract content between code blocks
            import re
            code_match = re.search(r'```(?:\w+)?\n?(.*?)\n?```', response, re.DOTALL)
            if code_match:
                return code_match.group(1).strip()
        
        return response.strip()

    def _generate_diffs(self, original_files: Dict[str, str], 
                       patched_files: Dict[str, str]) -> List[Dict[str, Any]]:
        """Generate unified diffs for the changes"""
        import difflib
        
        diffs = []
        for file_path in patched_files:
            if file_path in original_files:
                original_lines = original_files[file_path].splitlines(keepends=True)
                patched_lines = patched_files[file_path].splitlines(keepends=True)
                
                diff = list(difflib.unified_diff(
                    original_lines, patched_lines,
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                    lineterm=""
                ))
                
                if diff:
                    # Calculate lines added/removed
                    lines_added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
                    lines_removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
                    
                    diffs.append({
                        "filename": file_path,
                        "diff": "".join(diff),
                        "linesAdded": lines_added,
                        "linesRemoved": lines_removed
                    })
        
        return diffs
