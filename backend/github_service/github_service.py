
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service")

# Import local modules
from .github_client import GitHubClient
from .utils import is_test_mode, is_production, prepare_response_metadata

class GitHubService:
    """Service for GitHub operations"""

    def __init__(self):
        """Initialize GitHub service"""
        try:
            self.client = GitHubClient()
            self.test_mode = is_test_mode()
            self.production = is_production()
            self.allow_empty_commits = os.environ.get('ALLOW_EMPTY_COMMITS', 'false').lower() in ('true', 'yes', '1', 't')
            
            # Log environment info
            logger.info(f"Environment: {'Production' if self.production else 'Development'}, Test Mode: {self.test_mode}")
            
            logger.info("GitHub service initialized")
        except Exception as e:
            logger.error(f"Error initializing GitHub service: {str(e)}")
            raise

    def create_branch(self, ticket_id: str, base_branch: str = None) -> str:
        """Create a branch for fixing a bug"""
        # Log operation start
        logger.info("GitHub operation started: create_branch")
        logger.info(f"Operation details: {{'ticket_id': '{ticket_id}', 'branch_name': 'fix/{ticket_id.lower()}', 'base_branch': {base_branch}, 'test_mode': {self.test_mode}}}")
        
        try:
            # Create branch using client
            branch_name = f"fix/{ticket_id.lower()}"
            self.client.create_branch(branch_name, base_branch)
            
            # Log success
            logger.info("GitHub operation succeeded: create_branch")
            logger.info(f"Result details: {{'branch_name': '{branch_name}', 'ticket_id': '{ticket_id}'}}")
            logger.info(f"Successfully created branch {branch_name} for ticket {ticket_id}")
            
            return branch_name
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: create_branch")
            logger.error(f"Error details: {str(e)}")
            
            # Return branch name anyway since it might exist
            return f"fix/{ticket_id.lower()}"

    def commit_bug_fix(
        self, 
        branch_name: str, 
        file_paths: List[str],
        file_contents: List[str],
        ticket_id: str, 
        commit_message: str
    ) -> bool:
        """Commit bug fix to branch"""
        # Log operation start
        logger.info("GitHub operation started: commit_bug_fix")
        logger.info(f"Operation details: {{'ticket_id': '{ticket_id}', 'branch_name': '{branch_name}', 'file_count': {len(file_paths)}, 'environment': {'production' if self.production else 'development'}, 'test_mode': {self.test_mode}}}")
        
        # Validate inputs
        if not branch_name:
            logger.error("Branch name is required")
            return False
            
        if not file_paths or len(file_paths) == 0:
            logger.error("No file paths provided")
            return False
        
        # Ensure file_paths and file_contents have the same length
        if len(file_paths) != len(file_contents):
            logger.error(f"Mismatch in number of file paths ({len(file_paths)}) and contents ({len(file_contents)})")
            
            # If we have more paths than contents, truncate paths
            if len(file_paths) > len(file_contents):
                logger.warning(f"More file paths than content items, truncating to {len(file_contents)} files")
                file_paths = file_paths[:len(file_contents)]
            
            # If we have more contents than paths, truncate contents
            if len(file_contents) > len(file_paths):
                for i in range(len(file_paths), len(file_contents)):
                    logger.warning(f"More content items than file paths, ignoring extra content at index {i}")
                file_contents = file_contents[:len(file_paths)]
                
        # Check if we still have files to commit after validation
        if len(file_paths) == 0:
            logger.error("No valid file paths after filtering")
            return False
        
        try:
            # Prepare changes as a list of dictionaries
            changes = []
            for i in range(len(file_paths)):
                changes.append({
                    "path": file_paths[i],
                    "content": file_contents[i]
                })
            
            # Commit changes using client
            result = self.client.commit_changes(branch_name, changes, commit_message)
            
            # Check for empty commits
            if not result.get("committed", False) and result.get("error", {}).get("code") == "EMPTY_COMMIT":
                if self.allow_empty_commits:
                    logger.warning("Commit resulted in no changes, but ALLOW_EMPTY_COMMITS is true")
                    return True
                else:
                    logger.error("Commit resulted in no changes")
                    return False
            
            return result.get("committed", False)
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: commit_bug_fix")
            logger.error(f"Error details: {str(e)}")
            return False

    def create_pull_request(
        self, 
        branch_name: str, 
        ticket_id: str, 
        title: str, 
        description: str
    ) -> str:
        """Create a pull request for the branch"""
        # Log operation start
        logger.info("GitHub operation started: create_pull_request")
        
        try:
            # Create PR using client
            pr_url = self.client.create_pull_request(branch_name, title, description)
            
            # Log success
            logger.info("GitHub operation succeeded: create_pull_request")
            logger.info(f"Created PR: {pr_url} for ticket {ticket_id}")
            
            return pr_url
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: create_pull_request")
            logger.error(f"Error details: {str(e)}")
            return ""
    
    # Alias for create_pull_request to maintain backward compatibility
    def create_fix_pr(self, branch_name: str, ticket_id: str, title: str, description: str) -> str:
        """Alias for create_pull_request"""
        return self.create_pull_request(branch_name, ticket_id, title, description)

    def commit_patch(
        self, 
        branch_name: str, 
        patch_content: str, 
        commit_message: str,
        file_paths: List[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Commit changes using a patch"""
        # Log operation start
        logger.info("GitHub operation started: commit_patch")
        logger.info(f"Applying patch to branch {branch_name} with {len(file_paths)} files")
        
        try:
            # Validate patch content
            if not patch_content or not patch_content.strip():
                logger.error("Empty patch content provided")
                return False, {"error": {"code": "EMPTY_PATCH", "message": "Patch content is empty"}}
                
            # Validate file paths
            if not file_paths or len(file_paths) == 0:
                logger.error("No file paths provided for patch")
                return False, {"error": {"code": "NO_FILES", "message": "No file paths provided for patch"}}
            
            # Log the files that will be patched
            logger.info(f"Patching files: {file_paths}")
            
            # Apply patch using client
            result = self.client.apply_patch(branch_name, patch_content, commit_message, file_paths)
            
            # Log success or failure
            if result.get("committed", False):
                logger.info("GitHub operation succeeded: commit_patch")
                logger.info(f"Applied patch to {result.get('files_changed', 0)} files")
                return True, result
            else:
                logger.error(f"GitHub operation failed: commit_patch")
                logger.error(f"Error details: {result.get('error', {}).get('message', 'Unknown error')}")
                return False, result
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: commit_patch")
            logger.error(f"Error details: {str(e)}")
            return False, {"error": {"code": "EXCEPTION", "message": str(e)}}
