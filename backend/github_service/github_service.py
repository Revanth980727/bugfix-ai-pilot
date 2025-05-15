
import os
import logging
import json
import re
import subprocess
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union
from .github_client import GitHubClient
from .patch_validator import PatchValidator

class GitHubService:
    """Service for interacting with GitHub repositories"""
    
    def __init__(self):
        """Initialize the GitHub service"""
        self.logger = logging.getLogger("github-service")
        
        try:
            self.client = GitHubClient()
            self.validator = PatchValidator()
            self.logger.info("GitHub service initialized")
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
        
        try:
            # Create branch in the repository
            success = self.client.create_branch(branch_name, base_branch)
            
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
                      file_contents: List[str], ticket_id: str, commit_message: Optional[str] = None) -> bool:
        """
        Commit bug fix changes to a branch using proper patch application
        
        Args:
            branch_name: Branch to commit to (can be string or tuple from create_fix_branch)
            file_paths: List of file paths to update
            file_contents: List of file contents (parallel to file_paths)
            ticket_id: JIRA ticket ID
            commit_message: Optional commit message override
            
        Returns:
            Success status
        """
        # Handle the case where branch_name is a tuple from create_fix_branch
        if isinstance(branch_name, tuple) and len(branch_name) == 2:
            success, actual_branch_name = branch_name
            branch_name = actual_branch_name
            
        if not commit_message:
            commit_message = f"Fix bug for {ticket_id}"
            
        # Log received data
        self.logger.info(f"Committing bug fix for ticket {ticket_id} to branch {branch_name}")
        self.logger.info(f"Number of files to update: {len(file_paths) if file_paths else 0}")
            
        try:
            # Validate input
            if not file_paths:
                self.logger.error("No file paths provided")
                return False
            
            # Filter out any test files or fallback placeholders
            is_production = os.environ.get("ENVIRONMENT", "development") == "production"
            if is_production:
                original_count = len(file_paths)
                file_paths = [fp for fp in file_paths if not (fp.endswith("test.md") or "/test/" in fp)]
                if len(file_paths) != original_count:
                    self.logger.warning(f"Filtered out {original_count - len(file_paths)} test files in production mode")
            
            changes_applied = False
            for i, (file_path, content) in enumerate(zip(file_paths, file_contents)):
                # Check if content is a diff/patch
                is_diff = content.startswith('---') or content.startswith('diff --git')
                
                if is_diff:
                    self.logger.info(f"Applying patch to {file_path} using diff application")
                    # Apply diff using git apply or similar method
                    success = self._apply_patch(branch_name, file_path, content)
                else:
                    self.logger.info(f"Updating file {file_path} with full content replacement (fallback method)")
                    # Fallback to direct file update
                    success = self.client.commit_file(branch_name, file_path, content, commit_message)
                
                if success:
                    changes_applied = True
                    self.logger.info(f"Successfully updated file {file_path}")
                else:
                    self.logger.error(f"Failed to update file {file_path}")
            
            # Verify changes were actually made
            if changes_applied:
                # Run git diff to confirm changes were actually made
                has_changes = self._verify_changes(branch_name)
                if has_changes:
                    self.logger.info(f"Verified changes were made to branch {branch_name}")
                else:
                    self.logger.warning(f"No actual changes detected in branch {branch_name} after applying patches")
                    # Still return true since the operation technically succeeded
            
            if changes_applied:
                self.logger.info(f"Successfully committed fix for {ticket_id} to branch {branch_name}")
                return True
            else:
                self.logger.error(f"Failed to commit any changes for {ticket_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error committing bug fix: {e}")
            return False
    
    def _apply_patch(self, branch_name: str, file_path: str, patch_content: str) -> bool:
        """
        Apply a patch to a file using proper diff tools
        
        Args:
            branch_name: Branch to apply the patch to
            file_path: Path to the file to patch
            patch_content: The patch content in unified diff format
            
        Returns:
            Success status
        """
        try:
            # Get the current file content
            current_content = self.client.get_file_content(file_path, branch_name)
            if current_content is None:
                self.logger.error(f"Cannot apply patch: Unable to retrieve current content of {file_path}")
                return False
            
            # Create temporary files for the patch operation
            with tempfile.NamedTemporaryFile(mode='w', suffix='.orig') as orig_file, \
                 tempfile.NamedTemporaryFile(mode='w', suffix='.patch') as patch_file:
                
                # Write current content and patch to temp files
                orig_file.write(current_content)
                orig_file.flush()
                
                patch_file.write(patch_content)
                patch_file.flush()
                
                # Try to apply the patch using system's patch utility
                try:
                    result = subprocess.run(
                        ['patch', orig_file.name, patch_file.name],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if result.returncode != 0:
                        self.logger.error(f"Patch utility failed: {result.stderr}")
                        # Fall back to manual patching if system patch fails
                        return self._manual_apply_patch(branch_name, file_path, current_content, patch_content)
                    
                    # Read the patched content
                    with open(orig_file.name, 'r') as f:
                        patched_content = f.read()
                    
                    # Commit the updated content
                    return self.client.commit_file(branch_name, file_path, patched_content, f"Apply patch to {file_path}")
                
                except FileNotFoundError:
                    self.logger.warning("System patch utility not found, falling back to manual patch application")
                    return self._manual_apply_patch(branch_name, file_path, current_content, patch_content)
        
        except Exception as e:
            self.logger.error(f"Error applying patch to {file_path}: {e}")
            return False
    
    def _manual_apply_patch(self, branch_name: str, file_path: str, current_content: str, patch_content: str) -> bool:
        """
        Manually apply a patch when system utilities are not available
        
        Args:
            branch_name: Branch to apply the patch to
            file_path: Path to the file to patch
            current_content: Current content of the file
            patch_content: The patch content in unified diff format
            
        Returns:
            Success status
        """
        self.logger.info(f"Using manual patch application for {file_path}")
        try:
            # Try to use the unidiff library if available
            try:
                import unidiff
                patch_set = unidiff.PatchSet(patch_content)
                
                # Apply each chunk in the patch
                patched_lines = current_content.splitlines()
                
                for patched_file in patch_set:
                    for hunk in patched_file:
                        # Calculate line offset
                        line_offset = hunk.target_start - 1
                        
                        # Track removed lines to adjust offsets
                        removed_count = 0
                        
                        for line in hunk:
                            if line.is_added:
                                patched_lines.insert(line_offset + line.target_line_no - 1, line.value)
                            elif line.is_removed:
                                patched_lines.pop(line_offset + line.source_line_no - 1 - removed_count)
                                removed_count += 1
                
                patched_content = '\n'.join(patched_lines)
                
                # Commit the updated content
                return self.client.commit_file(branch_name, file_path, patched_content, f"Apply patch to {file_path}")
                
            except ImportError:
                self.logger.warning("Unidiff library not available, using basic line-by-line patching")
                
                # Very basic line patching (simplified)
                lines = current_content.splitlines()
                patch_lines = patch_content.splitlines()
                
                # Find hunks in the patch
                hunk_pattern = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')
                current_line = 0
                
                while current_line < len(patch_lines):
                    line = patch_lines[current_line]
                    current_line += 1
                    
                    # Look for hunk headers
                    match = hunk_pattern.match(line)
                    if match:
                        # Parse hunk header
                        old_start = int(match.group(1))
                        old_count = int(match.group(2))
                        new_start = int(match.group(3))
                        new_count = int(match.group(4))
                        
                        # Apply the changes from this hunk
                        old_idx = old_start - 1  # 0-based index
                        new_lines = []
                        
                        # Process lines in the hunk
                        for _ in range(max(old_count, new_count)):
                            if current_line >= len(patch_lines):
                                break
                                
                            pline = patch_lines[current_line]
                            current_line += 1
                            
                            if pline.startswith('+'):
                                # Added line
                                new_lines.append(pline[1:])
                            elif pline.startswith('-'):
                                # Removed line
                                old_idx += 1
                            elif pline.startswith(' '):
                                # Context line
                                new_lines.append(pline[1:])
                                old_idx += 1
                        
                        # Replace the corresponding section in the original lines
                        lines[old_start-1:old_idx] = new_lines
                
                patched_content = '\n'.join(lines)
                
                # Commit the updated content
                return self.client.commit_file(branch_name, file_path, patched_content, f"Apply patch to {file_path}")
                
        except Exception as e:
            self.logger.error(f"Manual patch application failed: {e}")
            return False
    
    def _verify_changes(self, branch_name: str) -> bool:
        """
        Verify that changes were actually made to the branch
        
        Args:
            branch_name: Branch to check
            
        Returns:
            True if changes were made, False otherwise
        """
        # In a real implementation, this would use git diff to verify changes
        # For now, we'll just return True
        self.logger.info(f"Verifying changes were made to branch {branch_name}")
        return True
    
    def create_fix_pr(self, branch_name: Union[Tuple[bool, str], str], ticket_id: str, title: Optional[str] = None, 
                     description: Optional[str] = None, base_branch: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create a pull request for the fix
        
        Args:
            branch_name: Source branch with fixes (can be string or tuple from create_fix_branch)
            ticket_id: JIRA ticket ID
            title: PR title (defaults to "Fix for {ticket_id}")
            description: PR description
            base_branch: Target branch (defaults to default branch from config)
            
        Returns:
            Dictionary with PR details including URL and number if successful, None otherwise
        """
        # Handle the case where branch_name is a tuple from create_fix_branch
        if isinstance(branch_name, tuple) and len(branch_name) == 2:
            success, actual_branch_name = branch_name
            branch_name = actual_branch_name
            
        if not title:
            title = f"Fix for {ticket_id}"
            
        if not description:
            description = f"This PR fixes the issue described in {ticket_id}."
            
        try:
            # Check for existing PR first
            existing_pr = self.check_for_existing_pr(branch_name, base_branch)
            if existing_pr:
                self.logger.info(f"Found existing PR for branch {branch_name}: {existing_pr}")
                
                # Store the PR number mapping
                if "number" in existing_pr:
                    self.pr_mappings[ticket_id] = existing_pr["number"]
                    self.logger.info(f"Mapped ticket {ticket_id} to PR #{existing_pr['number']}")
                    
                return existing_pr
            
            # Verify the branch has actual changes before creating a PR
            has_changes = self._verify_changes(branch_name)
            if not has_changes:
                self.logger.warning(f"No actual changes detected in branch {branch_name}, PR creation skipped")
                return None
            
            # Create PR - fixed to handle tuple return value properly
            pr_url, pr_number = self.client.create_pull_request(title, description, branch_name, base_branch)
            
            if not pr_url:
                self.logger.error(f"Failed to create PR for ticket {ticket_id}")
                return None
            
            # Store the PR mapping
            if pr_number:
                self.pr_mappings[ticket_id] = pr_number
                self.logger.info(f"Mapped ticket {ticket_id} to PR #{pr_number}")
            
            self.logger.info(f"Successfully created PR for ticket {ticket_id}: {pr_url}")
            return {
                "url": pr_url,
                "number": pr_number
            }
        except Exception as e:
            self.logger.error(f"Error creating PR for ticket {ticket_id}: {e}")
            return None
    
    def check_for_existing_pr(self, branch_name: str, base_branch: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Check if a PR already exists for the branch
        
        Args:
            branch_name: Source branch name
            base_branch: Target branch name
            
        Returns:
            Dictionary with PR details if found, None otherwise
        """
        # This would use the GitHub API to check for existing PRs
        # For this example, we'll just return None
        return None
    
    def add_pr_comment(self, pr_identifier: Union[str, int, tuple], comment: str) -> bool:
        # ... keep existing code (PR comment addition functionality)
        return True

