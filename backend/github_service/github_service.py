
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
    """Service for GitHub operations with diff-first approach"""

    def __init__(self):
        """Initialize GitHub service"""
        try:
            self.client = GitHubClient()
            self.test_mode = is_test_mode()
            self.production = is_production()
            self.allow_empty_commits = os.environ.get('ALLOW_EMPTY_COMMITS', 'false').lower() in ('true', 'yes', '1', 't')
            self.preserve_case = os.environ.get('PRESERVE_BRANCH_CASE', 'true').lower() in ('true', 'yes', '1', 't')
            
            # New: Diff-first configuration
            self.prefer_diffs = os.environ.get('PREFER_DIFFS', 'true').lower() in ('true', 'yes', '1', 't')
            self.allow_full_replace = os.environ.get('ALLOW_FULL_REPLACE', 'true').lower() in ('true', 'yes', '1', 't')
            self.require_confirmation_for_full_replace = os.environ.get('REQUIRE_CONFIRMATION_FULL_REPLACE', 'false').lower() in ('true', 'yes', '1', 't')
            
            # Log environment info
            logger.info(f"Environment: {'Production' if self.production else 'Development'}, Test Mode: {self.test_mode}")
            logger.info(f"Diff-first mode: {'Enabled' if self.prefer_diffs else 'Disabled'}")
            logger.info(f"Full replace allowed: {'Yes' if self.allow_full_replace else 'No'}")
            
            logger.info("GitHub service initialized with diff-first approach")
        except Exception as e:
            logger.error(f"Error initializing GitHub service: {str(e)}")
            raise

    def apply_changes(
        self, 
        branch_name: str, 
        changes: Union[str, List[Dict[str, str]], Dict[str, str]],
        commit_message: str,
        change_type: str = "auto"  # "diff", "files", "auto"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Apply changes using the most appropriate method (diff-first approach)
        
        Args:
            branch_name: Target branch
            changes: Either unified diff string, list of file dicts, or dict of file contents
            commit_message: Commit message
            change_type: Type hint for the changes ("diff", "files", "auto")
            
        Returns:
            Tuple of (success, result_details)
        """
        logger.info(f"Applying changes to branch {branch_name} using diff-first approach")
        logger.info(f"Change type: {change_type}, Prefer diffs: {self.prefer_diffs}")
        
        try:
            # Strategy 1: Try unified diff first (if available and preferred)
            if (change_type == "diff" or change_type == "auto") and isinstance(changes, str) and self.prefer_diffs:
                logger.info("Attempting to apply changes using unified diff (Strategy 1)")
                
                # Parse the diff to extract file paths
                parsed_changes = parse_patch_content(changes)
                patch_file_paths = [change.get('file_path', '') for change in parsed_changes if change.get('file_path')]
                
                if patch_file_paths:
                    result = self.commit_patch(
                        branch_name=branch_name,
                        patch_content=changes,
                        commit_message=commit_message,
                        patch_file_paths=patch_file_paths
                    )
                    
                    success, details = result
                    if success:
                        logger.info("✅ Strategy 1 (unified diff) succeeded")
                        details["method_used"] = "unified_diff"
                        details["strategy"] = "diff_first"
                        return True, details
                    else:
                        logger.warning(f"❌ Strategy 1 (unified diff) failed: {details.get('error', {}).get('message', 'Unknown error')}")
            
            # Strategy 2: Try file-based changes (fallback)
            if self.allow_full_replace:
                logger.info("Attempting to apply changes using file replacement (Strategy 2)")
                
                # Convert changes to file format if needed
                if isinstance(changes, str) and change_type == "auto":
                    # Try to extract file contents from diff (advanced parsing needed)
                    logger.warning("Cannot extract file contents from diff string, skipping Strategy 2")
                    return False, {"error": {"code": "CONVERSION_FAILED", "message": "Cannot convert diff to file contents"}}
                elif isinstance(changes, dict):
                    # changes is already a dict of filename -> content
                    file_paths = list(changes.keys())
                    file_contents = list(changes.values())
                elif isinstance(changes, list) and len(changes) > 0 and isinstance(changes[0], dict):
                    # changes is a list of dicts with filename/content
                    file_paths = [f.get("filename", f.get("path", "")) for f in changes]
                    file_contents = [f.get("content", "") for f in changes]
                else:
                    logger.error("Invalid changes format for Strategy 2")
                    return False, {"error": {"code": "INVALID_FORMAT", "message": "Invalid changes format"}}
                
                if self.require_confirmation_for_full_replace:
                    logger.warning("⚠️ Full file replacement requires confirmation but proceeding in automated mode")
                
                result = self.commit_bug_fix(
                    branch_name=branch_name,
                    files=file_paths,
                    file_contents_or_ticket_id=file_contents,
                    ticket_id_or_commit_message=commit_message
                )
                
                success, details = result
                if success:
                    logger.warning("⚠️ Strategy 2 (full file replacement) succeeded - consider improving diff generation")
                    details["method_used"] = "full_file_replacement"
                    details["strategy"] = "fallback"
                    details["warning"] = "Used full file replacement instead of diff"
                    return True, details
                else:
                    logger.error(f"❌ Strategy 2 (full file replacement) failed: {details.get('error', 'Unknown error')}")
            else:
                logger.error("Full file replacement is disabled and diff application failed")
                return False, {"error": {"code": "NO_FALLBACK", "message": "Diff failed and full replacement is disabled"}}
            
            # All strategies failed
            logger.error("❌ All change application strategies failed")
            return False, {"error": {"code": "ALL_STRATEGIES_FAILED", "message": "Both diff and file replacement strategies failed"}}
            
        except Exception as e:
            logger.error(f"Error in apply_changes: {str(e)}")
            return False, {"error": {"code": "EXCEPTION", "message": str(e)}}

    # ... keep existing code (create_branch, create_fix_branch, get_branch methods)

    def commit_bug_fix(
        self, 
        branch_name: str, 
        files: Union[List[Dict[str, str]], List[str]],
        file_contents_or_ticket_id: Union[List[str], str],
        ticket_id_or_commit_message: str, 
        commit_message: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Commit bug fix to branch with diff-first approach integration
        """
        # Log operation start with strategy info
        logger.info("GitHub operation started: commit_bug_fix (fallback strategy)")
        logger.warning("⚠️ Using full file replacement - consider improving diff generation for this case")
        
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
        
        logger.info(f"Operation details: {{'ticket_id': '{ticket_id}', 'branch_name': '{branch_name}', 'file_count': {len(file_paths)}, 'strategy': 'full_replacement'}}")
        
        # ... keep existing code (validation and commit logic)
        
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
        logger.info(f"Committing {len(file_paths)} files via full replacement, first {max_files_to_log}: {', '.join(file_paths[:max_files_to_log])}")
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
                    return True, {"message": "No changes detected but commit permitted", "files": file_paths, "method_used": "full_replacement"}
                else:
                    logger.error("Commit resulted in no changes")
                    return False, {"error": "Commit resulted in no changes", "code": "EMPTY_COMMIT"}
            
            success = result.get("committed", False)
            response = {"message": "Commit successful" if success else "Commit failed", "files": file_paths, "method_used": "full_replacement"}
            if success:
                response["warning"] = "Used full file replacement - consider improving diff generation"
            return success, response
        except Exception as e:
            # Log failure
            logger.error(f"GitHub operation failed: commit_bug_fix")
            logger.error(f"Error details: {str(e)}")
            return False, {"error": str(e)}

    # ... keep existing code (create_pull_request, create_fix_pr, find_pr_for_branch, check_for_existing_pr, add_pr_comment methods)

    def commit_patch(
        self, 
        branch_name: str, 
        patch_content: str, 
        commit_message: str,
        patch_file_paths: List[str],
        expected_content: Dict[str, str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Commit changes using a patch (primary method in diff-first approach)"""
        # Log operation start
        logger.info("GitHub operation started: commit_patch (primary strategy)")
        logger.info(f"Applying unified diff patch to branch {branch_name} with {len(patch_file_paths)} files")
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
                logger.info(f"Applied patch to {result.get('files_changed', 0)} files using unified diff")
                
                # Capture which method was used for each file (patch vs full replace)
                if "file_results" in result:
                    for file_path, file_result in result["file_results"].items():
                        method = file_result.get("method", "unknown")
                        if method == "full_replace":
                            logger.warning(f"File {file_path} used full replacement instead of patching")
                        else:
                            logger.info(f"File {file_path} patched successfully using {method}")
                
                # Add strategy information to result
                result["method_used"] = "unified_diff"
                result["strategy"] = "diff_first"
                
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

    # ... keep existing code (delete_branch method)
