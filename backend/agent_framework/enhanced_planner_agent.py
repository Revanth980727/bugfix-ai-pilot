
import re
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from .agent_base import Agent, AgentStatus
from ..repo_manager import repo_manager

class EnhancedPlannerAgent(Agent):
    def __init__(self):
        super().__init__(name="EnhancedPlannerAgent")
        self.output_dir = os.path.join(os.path.dirname(__file__), "planner_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a ticket using the actual repository"""
        self.set_status(AgentStatus.WORKING)
        
        try:
            # Ensure repository is available
            if not repo_manager.clone_repository():
                raise Exception("Failed to clone repository")
            
            ticket_id = ticket_data.get("ticket_id", "unknown")
            title = ticket_data.get("title", "")
            description = ticket_data.get("description", "")
            
            # Clean the ticket description
            cleaned_description = self._clean_ticket(description)
            
            # Get repository file list for validation
            repo_files = repo_manager.list_files()
            self.log(f"Found {len(repo_files)} files in repository")
            
            # Analyze the ticket with GPT
            analysis = self._analyze_with_gpt(ticket_id, title, cleaned_description, repo_files)
            
            # Validate affected files against repository
            if analysis.get("affected_files"):
                validated_files = self._validate_affected_files(analysis["affected_files"], repo_files)
                analysis["affected_files"] = validated_files
            
            self.set_status(AgentStatus.SUCCESS)
            return analysis
            
        except Exception as e:
            self.log(f"Error in planner agent: {str(e)}", level="error")
            self.set_status(AgentStatus.ERROR)
            
            # Return fallback analysis
            return self._generate_fallback_output(
                ticket_data.get("ticket_id", "unknown"), 
                ticket_data.get("description", "")
            )

    def _analyze_with_gpt(self, ticket_id: str, title: str, description: str, repo_files: List[str]) -> Dict[str, Any]:
        """Analyze ticket with GPT using repository context"""
        from ..openai_client import OpenAIClient
        
        # Create context about repository structure
        repo_context = self._create_repo_context(repo_files)
        
        prompt = f"""
        You are analyzing a bug ticket for a repository. Based on the ticket information and repository structure, identify:
        1. A brief summary of the bug
        2. Which files are likely affected (only include files that exist in the repository)
        3. The type of error/issue
        
        Repository files available:
        {repo_context}
        
        Ticket ID: {ticket_id}
        Title: {title}
        Description: {description}
        
        Respond ONLY with valid JSON in this format:
        {{
            "bug_summary": "Brief description of the bug",
            "affected_files": ["file1.py", "file2.js"],
            "error_type": "Type of error"
        }}
        """
        
        try:
            client = OpenAIClient()
            response = client.get_completion(prompt)
            
            # Validate and parse response
            is_valid, parsed_data, error = self._validate_gpt_response(response)
            
            if is_valid:
                parsed_data["ticket_id"] = ticket_id
                return parsed_data
            else:
                self.log(f"GPT response validation failed: {error}")
                raise Exception(f"Invalid GPT response: {error}")
                
        except Exception as e:
            self.log(f"Error getting GPT analysis: {str(e)}")
            raise

    def _create_repo_context(self, repo_files: List[str]) -> str:
        """Create a concise context of repository structure"""
        # Group files by extension for better context
        file_groups = {}
        for file_path in repo_files[:50]:  # Limit to first 50 files
            ext = os.path.splitext(file_path)[1]
            if ext not in file_groups:
                file_groups[ext] = []
            file_groups[ext].append(file_path)
        
        context_parts = []
        for ext, files in file_groups.items():
            if len(files) <= 5:
                context_parts.append(f"{ext} files: {', '.join(files)}")
            else:
                context_parts.append(f"{ext} files: {', '.join(files[:5])} (and {len(files)-5} more)")
        
        return "\n".join(context_parts)

    def _validate_affected_files(self, files: List[str], repo_files: List[str]) -> List[Dict[str, Any]]:
        """Validate file paths against repository structure"""
        validated_files = []
        repo_files_lower = [f.lower() for f in repo_files]
        
        for file_path in files:
            # Normalize path
            normalized = file_path.replace('\\', '/').lstrip('/')
            
            # Check exact match first
            if normalized in repo_files:
                validated_files.append({"file": normalized, "valid": True})
            # Check case-insensitive match
            elif normalized.lower() in repo_files_lower:
                # Find the actual file with correct case
                actual_file = next(f for f in repo_files if f.lower() == normalized.lower())
                validated_files.append({"file": actual_file, "valid": True})
            else:
                # Check for partial matches (file might be in subdirectory)
                partial_matches = [f for f in repo_files if f.endswith(normalized) or normalized in f]
                if partial_matches:
                    # Use the best match
                    best_match = min(partial_matches, key=len)
                    validated_files.append({"file": best_match, "valid": True})
                else:
                    validated_files.append({"file": file_path, "valid": False})
        
        return validated_files

    # ... keep existing code (_clean_ticket, _validate_gpt_response, _generate_fallback_output methods)
