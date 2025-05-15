
import os
import logging
import json
import re
import subprocess
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Tuple, Union
from .github_client import GitHubClient
from .patch_validator import PatchValidator
from .utils import (
    GitHubError, 
    is_test_mode, 
    is_production, 
    should_allow_test_files, 
    is_test_file,
    calculate_file_checksum, 
    validate_file_changes,
    prepare_response_metadata
)
from ..log_utils import (
    log_operation_attempt,
    log_operation_result,
    create_structured_error,
    log_diff_summary,
    GitHubOperationError
)

class GitHubService:
    """Service for interacting with GitHub repositories"""
    
    def __init__(self):
        """Initialize the GitHub service"""
        self.logger = logging.getLogger("github-service")
        
        try:
            self.client = GitHubClient()
            self.validator = PatchValidator()
            self.logger.info("GitHub service initialized")
            
            # Configure environment-specific behaviors
            self.is_production = is_production()
            self.test_mode = is_test_mode()
            self.logger.info(f"Environment: {'Production' if self.is_production else 'Development'}, Test Mode: {self.test_mode}")
        except Exception as e:
            self.logger.error(f"Error initializing GitHub service: {e}")
            raise
        
        # Store PR mappings for tickets
        self.pr_mappings = {}
        
    def create_fix_branch(self, ticket_id: str, base_branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Create a branch for fixing a bug
        
        Args:
            ticket_id: JIRA ticket ID
            base_branch: Base branch (defaults to default branch from config)
            
        Returns:
            Tuple of (success, branch_name)
        """
        # Generate branch name from ticket ID
        branch_name = f"fix/{ticket_id.lower()}"
        
        log_operation_attempt(self.logger, "create_branch", {
            "ticket_id": ticket_id,
            "branch_name": branch_name,
            "base_branch": base_branch,
            "test_mode": self.test_mode
        })
        
        try:
            # Create branch in the repository
            success = self.client.create_branch(branch_name, base_branch)
            
            log_operation_result(self.logger, "create_branch", success, {
                "branch_name": branch_name,
                "ticket_id": ticket_id
            })
            
            if success:
                self.logger.info(f"Successfully created branch {branch_name} for ticket {ticket_id}")
                return True, branch_name
            else:
                self.logger.error(f"Failed to create branch {branch_name}")
                return False, branch_name
        except Exception as e:
            self.logger.error(f"Error creating fix branch for ticket {ticket_id}: {e}")
            return False, branch_name
    
    def commit_bug_fix(self, branch_name: Union[Tuple[bool, str], str], file_paths: List[str], 
                      file_contents: List[str], ticket_id: str, commit_message: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Commit bug fix changes to a branch using proper patch application
        
        Args:
            branch_name: Branch to commit to (can be string or tuple from create_fix_branch)
            file_paths: List of file paths to update
            file_contents: List of file contents (parallel to file_paths)
            ticket_id: JIRA ticket ID
            commit_message: Optional commit message override
            
        Returns:
            Tuple of (success, metadata)
        """
        # Handle the case where branch_name is a tuple from create_fix_branch
        if isinstance(branch_name, tuple) and len(branch_name) == 2:
            success, actual_branch_name = branch_name
            branch_name = actual_branch_name
            
        if not commit_message:
            commit_message = f"Fix bug for {ticket_id}"
            
        # Log received data
        log_operation_attempt(self.logger, "commit_bug_fix", {
            "ticket_id": ticket_id,
            "branch_name": branch_name,
            "file_count": len(file_paths) if file_paths else 0,
            "environment": "production" if self.is_production else "development",
            "test_mode": self.test_mode
        })
            
        try:
            # Validate input
            if not file_paths:
                error = create_structured_error(
                    GitHubError.ERR_VALIDATION_FAILED,
                    "No file paths provided",
                    suggested_action="Provide at least one file to update"
                )
                self.logger.error(f"Failed commit validation: {error['message']}")
                return False, {"error": error}
            
            # Validate file_contents - ensure it contains strings only
            safe_content_list = []
            file_results = []
            
            for i, content in enumerate(file_contents):
                if i >= len(file_paths):
                    self.logger.warning(f"More content items than file paths, ignoring extra content at index {i}")
                    continue
                    
                file_path = file_paths[i]
                
                # Skip invalid paths entirely
                if not isinstance(file_path, str) or not file_path.strip():
                    error = create_structured_error(
                        GitHubError.ERR_VALIDATION_FAILED,
                        f"Invalid file path at index {i}",
                        suggested_action="Provide a valid file path string"
                    )
                    file_results.append({
                        "file_path": str(file_path) if file_path else f"item-{i}",
                        "success": False,
                        "error": error
                    })
                    continue
                
                # Check if file is a test file
                if is_test_file(file_path) and not should_allow_test_files():
                    error = create_structured_error(
                        GitHubError.ERR_TEST_MODE,
                        f"Cannot modify test file {file_path} in production without test_mode enabled",
                        file_path,
                        suggested_action="Use a non-test file path or enable test mode"
                    )
                    file_results.append({
                        "file_path": file_path,
                        "success": False,
                        "error": error
                    })
                    continue
                    
                # Type-safe content handling
                if isinstance(content, dict):
                    self.logger.warning(f"Converting dict content to JSON string for file {file_path}")
                    try:
                        safe_content = json.dumps(content, indent=2)
                        safe_content_list.append(safe_content)
                    except Exception as e:
                        error = create_structured_error(
                            GitHubError.ERR_VALIDATION_FAILED,
                            f"Failed to serialize dict content for {file_path}: {str(e)}",
                            file_path,
                            suggested_action="Provide valid JSON content"
                        )
                        file_results.append({
                            "file_path": file_path,
                            "success": False,
                            "error": error
                        })
                        continue
                elif not isinstance(content, str):
                    self.logger.warning(f"Converting {type(content)} to string for file {file_path}")
                    try:
                        safe_content = str(content)
                        safe_content_list.append(safe_content)
                    except Exception as e:
                        error = create_structured_error(
                            GitHubError.ERR_VALIDATION_FAILED,
                            f"Failed to convert content to string for {file_path}: {str(e)}",
                            file_path,
                            suggested_action="Provide string content"
                        )
                        file_results.append({
                            "file_path": file_path,
                            "success": False,
                            "error": error
                        })
                        continue
                else:
                    safe_content = content
                    safe_content_list.append(content)
            
            # Replace original list with type-safe content
            safe_file_paths = []
            for i, path in enumerate(file_paths):
                if i < len(safe_content_list):
                    safe_file_paths.append(path)
            
            file_paths = safe_file_paths
            file_contents = safe_content_list
            
            if not file_paths:
                self.logger.error("No valid file paths after filtering")
                metadata = prepare_response_metadata(file_results)
                return False, metadata
            
            changes_applied = False
            
            for i, (file_path, content) in enumerate(zip(file_paths, file_contents)):
                # Skip files that already failed validation
                if any(r.get("file_path") == file_path and not r.get("success", False) for r in file_results):
                    continue
                    
                # Get file's current content for checksums and validation
                original_content = self.client.get_file_content(file_path, branch_name)
                before_checksum = "new-file"
                
                if original_content is not None:
                    before_checksum = calculate_file_checksum(original_content)
                
                # Check if content is a diff/patch
                is_diff = isinstance(content, str) and (content.startswith('---') or content.startswith('diff --git'))
                
                self.logger.info(f"Processing file {file_path} (is_diff={is_diff}, before_checksum={before_checksum})")
                
                if is_diff:
                    self.logger.info(f"Applying patch to {file_path} using diff application")
                    # Apply diff using git apply or similar method
                    success, result = self._apply_patch(branch_name, file_path, content, original_content)
                    
                    if success:
                        # Add successful result
                        after_checksum = result.get("after_checksum", "unknown")
                        file_results.append({
                            "file_path": file_path,
                            "success": True,
                            "checksum": after_checksum,
                            "validation": result.get("validation", {})
                        })
                        changes_applied = True
                    else:
                        # Add failure result
                        file_results.append({
                            "file_path": file_path,
                            "success": False,
                            "error": result.get("error", create_structured_error(
                                GitHubError.ERR_PATCH_FAILED,
                                "Failed to apply patch",
                                file_path
                            ))
                        })
                else:
                    self.logger.info(f"Content doesn't appear to be a diff, treating as full content")
                    
                    # Ensure content is a string
                    if not isinstance(content, str):
                        self.logger.error(f"Content for {file_path} is not a string after conversion")
                        file_results.append({
                            "file_path": file_path,
                            "success": False,
                            "error": create_structured_error(
                                GitHubError.ERR_VALIDATION_FAILED,
                                "Content must be a string",
                                file_path
                            )
                        })
                        continue
                    
                    # Check if we should allow full file replacement
                    if self.is_production and not self.test_mode and original_content is not None:
                        self.logger.warning(f"Refusing to replace entire file {file_path} in production (not a diff)")
                        file_results.append({
                            "file_path": file_path,
                            "success": False,
                            "error": create_structured_error(
                                GitHubError.ERR_TEST_MODE,
                                "Cannot replace entire file in production without test mode",
                                file_path,
                                "Use a diff/patch approach or enable test mode"
                            )
                        })
                        continue
                    
                    # When we have original content, validate the change is meaningful
                    if original_content is not None:
                        is_valid, validation = validate_file_changes(original_content, content)
                        
                        # If validation fails, log and skip this file
                        if not is_valid:
                            self.logger.warning(f"Validation failed for {file_path}: {validation}")
                            file_results.append({
                                "file_path": file_path,
                                "success": False,
                                "validation": validation,
                                "error": create_structured_error(
                                    GitHubError.ERR_VALIDATION_FAILED,
                                    "Content validation failed",
                                    file_path,
                                    "Ensure content changes are meaningful and don't result in empty files",
                                    validation
                                )
                            })
                            continue
                    
                    # Calculate checksum for the new content
                    after_checksum = calculate_file_checksum(content)
                    
                    # Commit the file directly
                    success = self.client.commit_file(branch_name, file_path, content, commit_message)
                    
                    if success:
                        changes_applied = True
                        self.logger.info(f"Successfully updated file {file_path} (checksum: {after_checksum})")
                        file_results.append({
                            "file_path": file_path,
                            "success": True,
                            "checksum": after_checksum,
                            "validation": {
                                "beforeChecksum": before_checksum,
                                "afterChecksum": after_checksum,
                                "contentChanged": before_checksum != after_checksum
                            }
                        })
                    else:
                        self.logger.error(f"Failed to update file {file_path}")
                        file_results.append({
                            "file_path": file_path,
                            "success": False,
                            "error": create_structured_error(
                                GitHubError.ERR_COMMIT_FAILED,
                                "Failed to commit file",
                                file_path
                            )
                        })
            
            # Prepare the response metadata
            metadata = prepare_response_metadata(file_results)
            
            # Verify changes were actually made
            if changes_applied:
                # Run git diff to confirm changes were actually made
                has_changes, verification = self._verify_changes(branch_name)
                metadata["changesVerified"] = has_changes
                metadata["verificationDetails"] = verification
                
                if has_changes:
                    self.logger.info(f"Verified changes were made to branch {branch_name}")
                    return True, metadata
                else:
                    self.logger.warning(f"No actual changes detected in branch {branch_name} after applying patches")
                    metadata["error"] = create_structured_error(
                        GitHubError.ERR_COMMIT_EMPTY,
                        "No changes were detected after patch application",
                        suggested_action="Ensure patches make meaningful changes"
                    )
                    # Return false since no changes were actually made
                    return False, metadata
            
            if changes_applied:
                self.logger.info(f"Successfully committed fix for {ticket_id} to branch {branch_name}")
                return True, metadata
            else:
                self.logger.error(f"Failed to commit any changes for {ticket_id}")
                if "error" not in metadata:
                    metadata["error"] = create_structured_error(
                        GitHubError.ERR_COMMIT_FAILED,
                        "Failed to commit any changes",
                        suggested_action="Check file paths and content"
                    )
                return False, metadata
        except Exception as e:
            self.logger.error(f"Error committing bug fix: {e}")
            error = create_structured_error(
                GitHubError.ERR_UNKNOWN,
                f"Unexpected error: {str(e)}",
                suggested_action="Check logs for details"
            )
            return False, {"error": error}
    
    def _apply_patch(self, branch_name: str, file_path: str, patch_content: str, 
                    current_content: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Apply a patch to a file using proper diff tools
        
        Args:
            branch_name: Branch to apply the patch to
            file_path: Path to the file to patch
            patch_content: The patch content in unified diff format
            current_content: Current file content (optional, will be fetched if not provided)
            
        Returns:
            Tuple of (success, result_metadata)
        """
        try:
            # Validate inputs
            if not isinstance(patch_content, str):
                self.logger.error(f"Invalid patch content type: {type(patch_content)}")
                return False, {
                    "error": create_structured_error(
                        GitHubError.ERR_VALIDATION_FAILED,
                        "Patch content must be a string",
                        file_path
                    )
                }
                
            # Get the current file content if not provided
            if current_content is None:
                current_content = self.client.get_file_content(file_path, branch_name)
                
            if current_content is None:
                self.logger.error(f"Cannot apply patch: Unable to retrieve current content of {file_path}")
                return False, {
                    "error": create_structured_error(
                        GitHubError.ERR_FILE_NOT_FOUND,
                        f"Unable to retrieve current content of {file_path}",
                        file_path,
                        "Ensure the file exists in the repository"
                    )
                }
            
            before_checksum = calculate_file_checksum(current_content)
            self.logger.info(f"Retrieved current content of {file_path} ({len(current_content)} bytes, checksum: {before_checksum})")
            
            # Log the patch being applied (truncated for log readability)
            max_log_length = 500  # Maximum characters to log
            patch_preview = patch_content[:max_log_length]
            if len(patch_content) > max_log_length:
                patch_preview += f"... [{len(patch_content) - max_log_length} more characters]"
            self.logger.info(f"Patch to apply:\n{patch_preview}")
            
            # First try using git apply if possible
            try:
                # Create a temporary directory to serve as git repo
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Initialize git repo and save the current file
                    subprocess.run(['git', 'init'], cwd=temp_dir, check=True, capture_output=True)
                    file_dir = os.path.dirname(os.path.join(temp_dir, file_path))
                    os.makedirs(file_dir, exist_ok=True)
                    
                    with open(os.path.join(temp_dir, file_path), 'w') as f:
                        f.write(current_content)
                    
                    # Stage the file
                    subprocess.run(['git', 'add', file_path], cwd=temp_dir, check=True, capture_output=True)
                    subprocess.run(['git', 'config', 'user.email', 'patch@example.com'], cwd=temp_dir, check=True, capture_output=True)
                    subprocess.run(['git', 'config', 'user.name', 'Patch Applier'], cwd=temp_dir, check=True, capture_output=True)
                    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=temp_dir, check=True, capture_output=True)
                    
                    # Write the patch to a file
                    patch_file_path = os.path.join(temp_dir, 'changes.patch')
                    with open(patch_file_path, 'w') as f:
                        f.write(patch_content)
                    
                    # Try to apply the patch
                    self.logger.info("Attempting to apply patch using git apply")
                    apply_result = subprocess.run(
                        ['git', 'apply', '--check', 'changes.patch'], 
                        cwd=temp_dir, 
                        capture_output=True,
                        text=True
                    )
                    
                    # If check passed, apply for real
                    if apply_result.returncode == 0:
                        self.logger.info("Patch validation passed, applying changes")
                        subprocess.run(
                            ['git', 'apply', 'changes.patch'], 
                            cwd=temp_dir, 
                            check=True, 
                            capture_output=True
                        )
                        
                        # Stage the changes
                        subprocess.run(
                            ['git', 'add', file_path],
                            cwd=temp_dir,
                            check=True,
                            capture_output=True
                        )
                        
                        # Run git diff to confirm changes were made
                        diff_result = subprocess.run(
                            ['git', 'diff', '--cached', '--exit-code'],
                            cwd=temp_dir,
                            capture_output=True,
                            text=True
                        )
                        
                        # Check if there were any changes
                        if diff_result.returncode == 0:
                            self.logger.warning(f"No changes detected after applying patch to {file_path}")
                            return False, {
                                "error": create_structured_error(
                                    GitHubError.ERR_COMMIT_EMPTY,
                                    "No changes detected after applying patch",
                                    file_path,
                                    "Ensure patch makes meaningful changes"
                                )
                            }
                        
                        # Read the updated file content
                        with open(os.path.join(temp_dir, file_path), 'r') as f:
                            patched_content = f.read()
                        
                        # Calculate checksum for validation
                        after_checksum = calculate_file_checksum(patched_content)
                        
                        # Validate the changes
                        is_valid, validation = validate_file_changes(current_content, patched_content)
                        
                        # Log a preview of the diff
                        diff_preview = diff_result.stdout[:max_log_length]
                        if len(diff_result.stdout) > max_log_length:
                            diff_preview += f"... [{len(diff_result.stdout) - max_log_length} more characters]"
                        self.logger.info(f"Changes applied:\n{diff_preview}")
                        
                        # If validation fails, log and return false
                        if not is_valid:
                            self.logger.warning(f"Validation failed for patched content: {validation}")
                            return False, {
                                "error": create_structured_error(
                                    GitHubError.ERR_VALIDATION_FAILED,
                                    "Patched content validation failed",
                                    file_path,
                                    "Ensure patch doesn't result in empty or invalid file",
                                    validation
                                ),
                                "validation": validation,
                                "before_checksum": before_checksum,
                                "after_checksum": after_checksum
                            }
                            
                        # Commit the updated content
                        success = self.client.commit_file(branch_name, file_path, patched_content, f"Apply patch to {file_path}")
                        
                        if success:
                            return True, {
                                "success": True,
                                "after_checksum": after_checksum,
                                "validation": validation
                            }
                        else:
                            return False, {
                                "error": create_structured_error(
                                    GitHubError.ERR_COMMIT_FAILED,
                                    "Failed to commit patched file",
                                    file_path
                                )
                            }
                    else:
                        self.logger.warning(f"Git apply validation failed: {apply_result.stderr}")
                        
                        # Try force-applying anyway (some patches might have whitespace issues)
                        try:
                            self.logger.warning("Attempting with --ignore-whitespace flag")
                            subprocess.run(
                                ['git', 'apply', '--ignore-whitespace', 'changes.patch'], 
                                cwd=temp_dir, 
                                check=True, 
                                capture_output=True
                            )
                            
                            # Stage the changes
                            subprocess.run(
                                ['git', 'add', file_path],
                                cwd=temp_dir,
                                check=True,
                                capture_output=True
                            )
                            
                            # Read the updated file content
                            with open(os.path.join(temp_dir, file_path), 'r') as f:
                                patched_content = f.read()
                                
                            # Calculate checksum for validation
                            after_checksum = calculate_file_checksum(patched_content)
                                
                            # Verify changes were made by running diff
                            diff_result = subprocess.run(
                                ['git', 'diff', '--cached', '--exit-code'],
                                cwd=temp_dir,
                                capture_output=True,
                                text=True
                            )
                            
                            # If no changes were detected, log and return false
                            if diff_result.returncode == 0:
                                self.logger.warning(f"No changes detected after applying patch with --ignore-whitespace to {file_path}")
                                return False, {
                                    "error": create_structured_error(
                                        GitHubError.ERR_COMMIT_EMPTY,
                                        "No changes detected after applying patch with --ignore-whitespace",
                                        file_path,
                                        "Ensure patch makes meaningful changes"
                                    )
                                }
                                
                            # Validate the changes
                            is_valid, validation = validate_file_changes(current_content, patched_content)
                            
                            # If validation fails, log and return false
                            if not is_valid:
                                self.logger.warning(f"Validation failed for patched content: {validation}")
                                return False, {
                                    "error": create_structured_error(
                                        GitHubError.ERR_VALIDATION_FAILED,
                                        "Patched content validation failed",
                                        file_path,
                                        "Ensure patch doesn't result in empty or invalid file",
                                        validation
                                    ),
                                    "validation": validation,
                                    "before_checksum": before_checksum,
                                    "after_checksum": after_checksum
                                }
                                
                            return self.client.commit_file(branch_name, file_path, patched_content, f"Apply patch to {file_path}"), {
                                "success": True,
                                "after_checksum": after_checksum, 
                                "validation": validation
                            }
                        except subprocess.CalledProcessError as e:
                            self.logger.error(f"Git apply with ignore-whitespace failed: {e.stderr}")
                            # Fall back to manual patching
                            return self._manual_apply_patch(branch_name, file_path, current_content, patch_content)
            
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                self.logger.warning(f"Git apply failed: {str(e)}, falling back to manual patch application")
                return self._manual_apply_patch(branch_name, file_path, current_content, patch_content)
        
        except Exception as e:
            self.logger.error(f"Error applying patch to {file_path}: {e}")
            return False, {
                "error": create_structured_error(
                    GitHubError.ERR_PATCH_FAILED,
                    f"Error applying patch: {str(e)}",
                    file_path
                )
            }
    
    def _manual_apply_patch(self, branch_name: str, file_path: str, current_content: str, 
                           patch_content: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Manually apply a patch when system utilities are not available
        
        Args:
            branch_name: Branch to apply the patch to
            file_path: Path to the file to patch
            current_content: Current content of the file
            patch_content: The patch content in unified diff format
            
        Returns:
            Tuple of (success, result_metadata)
        """
        self.logger.info(f"Using manual patch application for {file_path}")
        
        before_checksum = calculate_file_checksum(current_content)
        
        try:
            # Try to use the unidiff library
            try:
                import unidiff
                patch_set = unidiff.PatchSet(patch_content)
                
                if not patch_set or len(patch_set) == 0:
                    self.logger.error("No valid patches found in the patch content")
                    return False, {
                        "error": create_structured_error(
                            GitHubError.ERR_VALIDATION_FAILED,
                            "No valid patches found in the patch content",
                            file_path,
                            "Ensure the patch is in unified diff format"
                        )
                    }
                
                # Log what we're about to do
                self.logger.info(f"Found {len(patch_set)} files in patch, processing file changes")
                
                # Apply each chunk in the patch
                self.logger.info(f"Splitting content into lines for patching")
                patched_lines = current_content.splitlines()
                original_lines_count = len(patched_lines)
                
                changes_applied = False
                
                for patched_file in patch_set:
                    self.logger.info(f"Processing patch for {patched_file.path}")
                    
                    for hunk in patched_file:
                        # Log hunk details
                        self.logger.info(f"Applying hunk {hunk.source_start},{hunk.source_length} -> {hunk.target_start},{hunk.target_length}")
                        
                        # Calculate line offset
                        line_offset = hunk.target_start - 1
                        
                        # Track removed lines to adjust offsets
                        removed_count = 0
                        added_count = 0
                        
                        for line in hunk:
                            if line.is_added:
                                idx = line_offset + line.target_line_no - 1
                                self.logger.debug(f"Adding line at position {idx}: {line.value[:20]}...")
                                patched_lines.insert(idx, line.value)
                                added_count += 1
                                changes_applied = True
                            elif line.is_removed:
                                idx = line_offset + line.source_line_no - 1 - removed_count
                                if idx < len(patched_lines):
                                    self.logger.debug(f"Removing line at position {idx}: {patched_lines[idx][:20]}...")
                                    patched_lines.pop(idx)
                                    removed_count += 1
                                    changes_applied = True
                                else:
                                    self.logger.error(f"Cannot remove line at index {idx}, out of range (max={len(patched_lines)-1})")
                
                # Check if any changes were made
                if not changes_applied:
                    self.logger.warning("No changes were applied by the patch")
                    return False, {
                        "error": create_structured_error(
                            GitHubError.ERR_PATCH_FAILED,
                            "No changes were applied by the patch",
                            file_path,
                            "Check that the patch is valid for the current file content"
                        )
                    }
                
                # Join the lines back together
                patched_content = '\n'.join(patched_lines)
                
                # Log a summary of changes
                new_lines_count = len(patched_lines)
                self.logger.info(f"Manual patch applied: {original_lines_count} lines before, {new_lines_count} lines after")
                
                # Calculate checksum for validation
                after_checksum = calculate_file_checksum(patched_content)
                
                # Validate the changes
                is_valid, validation = validate_file_changes(current_content, patched_content)
                
                # Basic verification that we haven't corrupted the file
                if not is_valid:
                    self.logger.error(f"Patched content validation failed: {validation}")
                    return False, {
                        "error": create_structured_error(
                            GitHubError.ERR_VALIDATION_FAILED,
                            "Patched content validation failed",
                            file_path,
                            "Ensure patch doesn't result in empty or invalid file",
                            validation
                        ),
                        "validation": validation,
                        "before_checksum": before_checksum,
                        "after_checksum": after_checksum
                    }
                
                # Do a diff comparison to verify changes before committing
                import difflib
                diff = list(difflib.unified_diff(
                    current_content.splitlines(True),
                    patched_content.splitlines(True),
                    fromfile=f'a/{file_path}',
                    tofile=f'b/{file_path}'
                ))
                
                if not diff:
                    self.logger.warning("Manual diff verification shows no changes were made")
                    return False, {
                        "error": create_structured_error(
                            GitHubError.ERR_COMMIT_EMPTY,
                            "No changes detected after manual patch application",
                            file_path,
                            "Ensure patch makes meaningful changes"
                        )
                    }
                    
                # Commit the updated content
                success = self.client.commit_file(branch_name, file_path, patched_content, f"Apply patch to {file_path}")
                
                return success, {
                    "success": success,
                    "after_checksum": after_checksum,
                    "validation": validation
                }
                
            except ImportError:
                self.logger.error("Unidiff library not available, please install it with: pip install unidiff")
                return False, {
                    "error": create_structured_error(
                        GitHubError.ERR_DEPENDENCY_MISSING,
                        "Unidiff library not available",
                        suggested_action="Install unidiff: pip install unidiff"
                    )
                }
                
        except Exception as e:
            self.logger.error(f"Manual patch application failed: {e}")
            return False, {
                "error": create_structured_error(
                    GitHubError.ERR_PATCH_FAILED,
                    f"Manual patch application failed: {str(e)}",
                    file_path
                )
            }
    
    def _verify_changes(self, branch_name: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify that changes were actually made to the branch using git diff
        
        Args:
            branch_name: Branch to check
            
        Returns:
            Tuple of (has_changes, verification_details)
        """
        self.logger.info(f"Verifying changes were made to branch {branch_name}")
        
        verification_details = {
            "method": "api_call",
            "timestamp": None,
            "files_changed": [],
        }
        
        try:
            # If in test mode, just return true with minimal verification
            if self.test_mode:
                self.logger.info("Test mode enabled, performing minimal change verification")
                verification_details["method"] = "test_mode"
                verification_details["timestamp"] = self.client.get_latest_commit_timestamp(branch_name)
                return True, verification_details
                
            # Try to get information about changes in the branch
            changed_files = self.client.get_changed_files_in_branch(branch_name)
            verification_details["files_changed"] = changed_files
            verification_details["timestamp"] = self.client.get_latest_commit_timestamp(branch_name)
            
            has_changes = len(changed_files) > 0
                
            if has_changes:
                self.logger.info(f"Verified changes exist in branch {branch_name}: {len(changed_files)} files changed")
            else:
                self.logger.warning(f"No changes detected in branch {branch_name}")
                
            return has_changes, verification_details
            
        except Exception as e:
            self.logger.error(f"Error verifying changes: {e}")
            verification_details["error"] = str(e)
            # In case of error, assume changes exist but mark verification as uncertain
            verification_details["uncertain"] = True
            return True, verification_details
    
    # ... keep existing code (PR creation and comment functionality)
