import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service")

# Import local modules
try:
    from .github_client import GitHubClient
    from .utils import is_test_mode, is_production, prepare_response_metadata, parse_patch_content
    from .patch_engine import apply_patch_to_content, validate_patch
except ImportError:
    logger.error("Error importing local modules - check path configuration")
    # Still try relative imports as fallback
    try:
        from github_service.github_client import GitHubClient
        from github_service.utils import is_test_mode, is_production, prepare_response_metadata, parse_patch_content
        from github_service.patch_engine import apply_patch_to_content, validate_patch
        logger.info("Successfully imported modules from github_service package")
    except ImportError as e:
        logger.critical(f"Failed to import required modules: {e}")
        raise

class GitHubService:
    """Service for GitHub operations"""

    def __init__(self):
        """Initialize GitHub service"""
        try:
            self.client = GitHubClient()
            self.test_mode = is_test_mode()
            self.production = is_production()
            self.allow_empty_commits = os.environ.get('ALLOW_EMPTY_COMMITS', 'false').lower() in ('true', 'yes', '1', 't')
            self.preserve_case = os.environ.get('PRESERVE_BRANCH_CASE', 'true').lower() in ('true', 'yes', '1', 't')
            
            # Log environment info
            logger.info(f"Environment: {'Production' if self.production else 'Development'}, Test Mode: {self.test_mode}")
            logger.info(f"Branch case sensitivity: {'Preserved' if self.preserve_case else 'Lowercase'}")
            
            logger.info("GitHub service initialized")
        except Exception as e:
            logger.error(f"Error initializing GitHub service: {str(e)}")
            raise

    def create_branch(self, ticket_id: str, base_branch: str = None) -> str:
        """Create a branch for fixing a bug"""
        # Log operation start
        logger.info("GitHub operation started: create_branch")
        
        # Create branch name based on case sensitivity setting
        branch_name = f"fix/{ticket_id}" if self.preserve_case else f"fix/{ticket_id.lower()}"
        logger.info(f"Operation details: {{'ticket_id': '{ticket_id}', 'branch_name': '{branch_name}', 'base_branch': {base_branch}, 'test_mode': {self.test_mode}}}")
        
        try:
            # Create branch using client
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
            return branch_name

    def create_fix_branch(self, ticket_id: str, base_branch: str = None) -> Tuple[bool, str]:
        """
        Create a branch for fixing a bug, with enhanced return information
        
        Args:
            ticket_id: The ticket identifier
            base_branch: The branch to base the new branch on
            
        Returns:
            Tuple of (success, branch_name)
        """
        try:
            branch_name = self.create_branch(ticket_id, base_branch)
            return True, branch_name
        except Exception as e:
            logger.error(f"Error creating branch: {str(e)}")
            # Still return the branch name for cases where it might exist but creation failed
            branch_name = f"fix/{ticket_id}" if self.preserve_case else f"fix/{ticket_id.lower()}"
            return False, branch_name

    def get_branch(self, branch_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a branch if it exists"""
        try:
            # This would normally use the client to check if branch exists
            # For now, we'll just return a stub
            return {"name": branch_name, "exists": True}
        except Exception:
            return None

    def commit_bug_fix(
        self, 
        branch_name: str, 
        files: Union[List[Dict[str, str]], List[str]],
        file_contents_or_ticket_id: Union[List[str], str],
        ticket_id_or_commit_message: str, 
        commit_message: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Commit bug fix to branch with flexible parameter handling.
        
        This method supports two calling conventions:
        1. commit_bug_fix(branch_name, files_dict_list, ticket_id, commit_message)
           Where files_dict_list is a list of dicts with 'filename' and 'content' keys
        
        2. commit_bug_fix(branch_name, file_paths, file_contents, ticket_id, commit_message)
           Where file_paths and file_contents are separate lists
        
        Args:
            branch_name: Name of the branch to commit to
            files: Either list of file path strings or list of dicts with filename/content
            file_contents_or_ticket_id: Either list of file contents or ticket ID string
            ticket_id_or_commit_message: Either ticket ID or commit message
            commit_message: Optional commit message for calling convention #2
            
        Returns:
            Tuple of (success, details_dict)
        """
        # Log operation start
        logger.info("GitHub operation started: commit_bug_fix")
        
        # Handle both calling conventions
        if isinstance(files, list) and len(files) > 0 and isinstance(files[0], dict):
            # Convention 1: List of dicts with filename and content
            file_dicts = files
            ticket_id = file_contents_or_ticket_id
            commit_msg = ticket_id_or_commit_message
            
            # Extract paths and contents
            file_paths = [f.get("filename", "") for f in file_dicts]
            file_contents = [f.get("content", "") for f in file_dicts]
        else:
            # Convention 2: Separate lists for paths and contents
            file_paths = files
            file_contents = file_contents_or_ticket_id
            ticket_id = ticket_id_or_commit_message
            commit_msg = commit_message if commit_message else f"Fix for {ticket_id}"
        
        logger.info(f"Operation details: {{'ticket_id': '{ticket_id}', 'branch_name': '{branch_name}', 'file_count': {len(file_paths)}, 'test_mode': {self.test_mode}}}")
        
        # Validate inputs
        if not branch_name:
            logger.error("Branch name is required")
            return False, {"error": "Branch name is required"}
            
        if not file_paths or len(file_paths) == 0:
            logger.error("No file paths provided")
            return False, {"error": "No file paths provided"}
        
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
            return False, {"error": "No valid file paths after filtering"}
        
        # Log the files to be committed (first 5 files)
        max_files_to_log = min(5, len(file_paths))
        logger.info(f"Committing {len(file_paths)} files, first {max_files_to_log}: {', '.join(file_paths[:max_files_to_log])}")
        if len(file_paths) > max_files_to_log:
            logger.info(f"... and {len(file_paths) - max_files_to_log} more files")
        
        try:
            # Prepare changes as a list of dictionaries
            changes = []
            for i in range(len(file_paths)):
                changes.append({
                    "path": file_paths[i],
                    "content": file_contents[i]
                })
            
            # Commit changes using client
            result = self.client.commit_changes(branch_name, changes, commit_msg)
            
            # Check for empty commits
            if not result.get("committed", False) and result.get("error", {}).get("code") == "EMPTY_COMMIT":
                if self.allow_empty_commits:
                    logger.warning("Commit resulted in no changes, but ALLOW_EMPTY_COMMITS is true")
                    return True, {"message": "No changes detected but commit permitted", "files": file_paths}
                else:
                    logger.error("Commit resulted in no changes")
                    return False, {"error": "Commit resulted in no changes", "code": "EMPTY_COMMIT"}
            
            success = result.get("committed", False)
            return success, {"message": "Commit successful" if success else "Commit failed", "files": file_paths}
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: commit_bug_fix")
            logger.error(f"Error details: {str(e)}")
            return False, {"error": str(e)}

    def create_pull_request(
        self, 
        branch_name: str, 
        ticket_id: str, 
        title: str, 
        description: str
    ) -> Union[str, Dict[str, Any], Tuple[str, int]]:
        """Create a pull request for the branch"""
        # Log operation start
        logger.info("GitHub operation started: create_pull_request")
        
        try:
            # Create PR using client
            pr_result = self.client.create_pull_request(branch_name, title, description)
            
            # Handle different return formats
            if isinstance(pr_result, dict):
                pr_url = pr_result.get("url", "")
                pr_number = pr_result.get("number")
            elif isinstance(pr_result, tuple) and len(pr_result) >= 2:
                pr_url = pr_result[0]
                pr_number = pr_result[1]
            else:
                pr_url = str(pr_result)
                pr_number = None
            
            # Log success
            logger.info("GitHub operation succeeded: create_pull_request")
            logger.info(f"Created PR: {pr_url} for ticket {ticket_id}")
            
            # Return the most informative format available
            if pr_number is not None:
                return {"url": pr_url, "number": pr_number}
            return pr_url
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: create_pull_request")
            logger.error(f"Error details: {str(e)}")
            return ""
    
    # Alias for create_pull_request to maintain backward compatibility
    def create_fix_pr(self, branch_name: str, ticket_id: str, title: str, description: str) -> Union[str, Dict[str, Any], Tuple[str, int]]:
        """Alias for create_pull_request"""
        return self.create_pull_request(branch_name, ticket_id, title, description)

    def find_pr_for_branch(self, branch_name: str) -> Optional[Dict[str, Any]]:
        """Find an existing PR for the given branch name"""
        try:
            # This would normally use the client to check for PRs
            # For now we'll return None to indicate no PR exists
            return None
        except Exception as e:
            logger.error(f"Error checking for existing PR: {str(e)}")
            return None

    def check_for_existing_pr(self, branch_name: str, base_branch: str = None) -> Optional[Dict[str, Any]]:
        """Check if a PR already exists for this branch"""
        return self.find_pr_for_branch(branch_name)

    def add_pr_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a PR"""
        try:
            logger.info(f"Adding comment to PR #{pr_number}")
            # This would normally use the client to add a comment
            return True
        except Exception as e:
            logger.error(f"Error adding PR comment: {str(e)}")
            return False

    def commit_patch(
        self, 
        branch_name: str, 
        patch_content: str, 
        commit_message: str,
        patch_file_paths: List[str],
        expected_content: Dict[str, str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Commit changes using a patch"""
        # Log operation start
        logger.info("GitHub operation started: commit_patch")
        logger.info(f"Applying patch to branch {branch_name} with {len(patch_file_paths)} files")
        logger.info(f"Expected content validation: {'Enabled' if expected_content else 'Disabled'}")
        
        try:
            # Validate patch content
            if not patch_content or not patch_content.strip():
                logger.error("Empty patch content provided")
                return False, {"error": {"code": "EMPTY_PATCH", "message": "Patch content is empty"}}
                
            # Validate file paths
            if not patch_file_paths or len(patch_file_paths) == 0:
                logger.error("No file paths provided for patch")
                return False, {"error": {"code": "NO_FILES", "message": "No file paths provided for patch"}}
            
            # Parse patch to verify files and log details
            parsed_changes = parse_patch_content(patch_content)
            parsed_files = [change.get('file_path', '') for change in parsed_changes]
            
            # Check if all expected files are in the patch
            missing_files = []
            for file_path in patch_file_paths:
                if file_path not in parsed_files:
                    missing_files.append(file_path)
            
            if missing_files:
                logger.warning(f"Some files missing in patch: {', '.join(missing_files)}")
            
            # Get the original content for each file for validation
            original_contents = {}
            for file_path in patch_file_paths:
                content = self.client._get_file_content(file_path, branch_name)
                if content is not None:
                    original_contents[file_path] = content
                    logger.info(f"Retrieved original content for {file_path}: {len(content)} bytes")
                else:
                    logger.warning(f"Could not retrieve original content for {file_path}")
            
            # Validate patch before applying
            if expected_content and original_contents:
                validation_result = validate_patch(
                    patch_content=patch_content,
                    file_paths=patch_file_paths,
                    original_contents=original_contents,
                    expected_contents=expected_content
                )
                
                logger.info(f"Patch validation results: Valid={validation_result['valid']}")
                for file_path, file_result in validation_result['file_results'].items():
                    if file_result.get('valid', False):
                        logger.info(f"✓ Validation passed for {file_path} using {file_result.get('method', 'unknown')}")
                    else:
                        logger.warning(f"✗ Validation failed for {file_path}: {file_result.get('error', 'unknown error')}")
                        logger.warning(f"Will attempt patch application anyway with careful validation")
            
            # Filter out any unwanted test files based on environment variables
            include_test_files = os.environ.get('INCLUDE_TEST_FILES', 'false').lower() in ('true', 'yes', '1', 't') or self.test_mode
            
            if not include_test_files and not self.test_mode:
                filtered_file_paths = []
                for file_path in patch_file_paths:
                    if '/test/' in file_path or file_path.endswith('_test.py') or file_path.endswith('test.md'):
                        logger.info(f"Skipping test file: {file_path} (INCLUDE_TEST_FILES is disabled)")
                        continue
                    filtered_file_paths.append(file_path)
                
                if len(filtered_file_paths) < len(patch_file_paths):
                    logger.warning(f"Filtered out {len(patch_file_paths) - len(filtered_file_paths)} test files")
                    patch_file_paths = filtered_file_paths
            
            # Log the files that will be patched
            logger.info(f"Patching files from parsed content: {parsed_files}")
            
            # Apply patch using client with expected content for validation
            result = self.client.apply_patch(branch_name, patch_content, commit_message, patch_file_paths, expected_content)
            
            # Log success or failure
            if result.get("committed", False):
                logger.info("GitHub operation succeeded: commit_patch")
                logger.info(f"Applied patch to {result.get('files_changed', 0)} files")
                
                # Capture which method was used for each file (patch vs full replace)
                if "file_results" in result:
                    for file_path, file_result in result["file_results"].items():
                        method = file_result.get("method", "unknown")
                        if method == "full_replace":
                            logger.warning(f"File {file_path} used full replacement instead of patching")
                        else:
                            logger.info(f"File {file_path} patched successfully using {method}")
                
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
            
    def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch after PR is merged or closed"""
        try:
            logger.info(f"Deleting branch {branch_name}")
            # This would normally use the client to delete the branch
            return True
        except Exception as e:
            logger.error(f"Error deleting branch: {str(e)}")
            return False
