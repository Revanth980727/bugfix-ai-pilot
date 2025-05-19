
import os
import sys
import logging
import traceback
from typing import Dict, List, Any, Union, Optional
from datetime import datetime
from io import StringIO

# Try to import PyGithub
try:
    from github import Github, GithubException, UnknownObjectException
    from github.Repository import Repository
    from github.Branch import Branch
    from github.ContentFile import ContentFile
except ImportError:
    logging.error("Failed to import PyGithub - make sure it's installed")
    raise

# Try to import unidiff for proper patch parsing
try:
    import unidiff
except ImportError:
    logging.error("Failed to import unidiff - make sure it's installed")
    unidiff = None

# Configure logger
logger = logging.getLogger("github-client")

# Get environment variables
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO_OWNER = os.environ.get('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.environ.get('GITHUB_REPO_NAME')
GITHUB_DEFAULT_BRANCH = os.environ.get('GITHUB_DEFAULT_BRANCH', 'main')
GITHUB_USE_DEFAULT_BRANCH_ONLY = os.environ.get('GITHUB_USE_DEFAULT_BRANCH_ONLY', 'false').lower() in ('true', 'yes', '1', 't')
TEST_MODE = os.environ.get('TEST_MODE', 'false').lower() in ('true', 'yes', '1', 't')

class GitHubClient:
    """Client for interacting with GitHub API"""

    def __init__(self):
        """Initialize GitHub client"""
        try:
            if TEST_MODE:
                logger.info("Initializing GitHub client in TEST MODE - using mock API")
                self.init_test_mode()
            else:
                logger.info("Initializing GitHub client in PRODUCTION MODE - using real GitHub API")
                self.init_production_mode()
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {str(e)}")
            traceback.print_exc()
            raise

    def init_production_mode(self):
        """Initialize client for production use with real GitHub API"""
        if not GITHUB_TOKEN:
            raise ValueError("GitHub token not provided")
            
        if not GITHUB_REPO_OWNER or not GITHUB_REPO_NAME:
            raise ValueError("GitHub repository information not provided")
        
        # Create GitHub client
        self.github = Github(GITHUB_TOKEN)
        
        # Get repository
        self.repo = self.github.get_repo(f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        logger.info(f"GitHub client initialized with repo {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
        
        # Get default branch
        self.default_branch_name = GITHUB_DEFAULT_BRANCH
        logger.info(f"Default branch: {self.default_branch_name}")
        logger.info(f"Use default branch only: {GITHUB_USE_DEFAULT_BRANCH_ONLY}")
        
    def init_test_mode(self):
        """Initialize client for test mode with mocked functionality"""
        logger.warning("Running in TEST MODE - using mock GitHub implementation")
        
        # Set up mock attributes
        self.github = None
        self.repo = None
        self.default_branch_name = GITHUB_DEFAULT_BRANCH or 'main'
        
        # Mock data
        self.mock_branches = ["main", "develop"]
        self.mock_files = {}

    def create_branch(self, branch_name: str, base_branch: str = None) -> str:
        """Create a branch in the repository"""
        if TEST_MODE:
            return self._mock_create_branch(branch_name)
            
        try:
            # Check if branch already exists
            try:
                logger.info(f"Checking if branch {branch_name} exists")
                existing_branch = self.repo.get_branch(branch_name)
                logger.info(f"Branch {branch_name} exists")
                logger.warning(f"Branch {branch_name} already exists")
                return branch_name
            except GithubException:
                # Branch doesn't exist, proceed with creation
                pass
                
            # Get base branch
            if not base_branch:
                base_branch = self.default_branch_name
                
            # Get the base branch ref
            base_ref = self.repo.get_git_ref(f"heads/{base_branch}")
            
            # Create new branch
            self.repo.create_git_ref(f"refs/heads/{branch_name}", base_ref.object.sha)
            logger.info(f"Created branch {branch_name} from {base_branch}")
            
            return branch_name
        except Exception as e:
            logger.error(f"Error creating branch {branch_name}: {str(e)}")
            return ""

    # ... keep existing code (_mock_create_branch)

    def commit_changes(
        self, 
        branch_name: str, 
        changes: List[Dict[str, str]], 
        commit_message: str
    ) -> Dict[str, Any]:
        """Commit changes to files in the repository"""
        if TEST_MODE:
            return self._mock_commit_changes(branch_name, changes, commit_message)
        
        try:
            # Track if anything was actually changed
            files_changed = 0
            
            # Process each file change
            for change in changes:
                file_path = change.get("path")
                content = change.get("content")
                
                if not file_path or not content:
                    logger.warning(f"Skipping invalid change: missing path or content")
                    continue
                
                try:
                    # Check if file exists
                    try:
                        file = self.repo.get_contents(file_path, ref=branch_name)
                        # Update file
                        if file.decoded_content.decode('utf-8') != content:
                            self.repo.update_file(
                                path=file_path,
                                message=f"{commit_message} - Update {file_path}",
                                content=content,
                                sha=file.sha,
                                branch=branch_name
                            )
                            files_changed += 1
                            logger.info(f"Updated file {file_path}")
                        else:
                            logger.info(f"File {file_path} unchanged, skipping")
                    except UnknownObjectException:
                        # Create new file
                        self.repo.create_file(
                            path=file_path,
                            message=f"{commit_message} - Create {file_path}",
                            content=content,
                            branch=branch_name
                        )
                        files_changed += 1
                        logger.info(f"Created file {file_path}")
                except Exception as inner_e:
                    logger.error(f"Error processing file {file_path}: {str(inner_e)}")
            
            # Check if anything was committed
            if files_changed > 0:
                logger.info(f"Committed {files_changed} files to {branch_name}")
                return {"committed": True, "files_changed": files_changed}
            else:
                logger.warning(f"No files were changed in this commit")
                return {
                    "committed": False, 
                    "error": {"code": "EMPTY_COMMIT", "message": "No files were changed in this commit"}
                }
                
        except Exception as e:
            logger.error(f"Error committing changes: {str(e)}")
            return {"committed": False, "error": {"code": "COMMIT_ERROR", "message": str(e)}}

    # ... keep existing code (_mock_commit_changes)

    def create_pull_request(self, branch_name: str, title: str, description: str) -> str:
        """Create a pull request from branch to default branch"""
        if TEST_MODE:
            return self._mock_create_pull_request(branch_name, title, description)
            
        try:
            # Create PR
            base_branch = self.default_branch_name
            pr = self.repo.create_pull(
                title=title,
                body=description,
                head=branch_name,
                base=base_branch
            )
            
            logger.info(f"Created PR #{pr.number}: {pr.html_url}")
            return pr.html_url
        except Exception as e:
            logger.error(f"Error creating PR for {branch_name}: {str(e)}")
            return ""

    # ... keep existing code (_mock_create_pull_request)

    def apply_patch(
        self, 
        branch_name: str, 
        patch_content: str, 
        commit_message: str, 
        file_paths: List[str]
    ) -> Dict[str, Any]:
        """Apply a patch to the repository"""
        if TEST_MODE:
            return self._mock_apply_patch(branch_name, patch_content, commit_message, file_paths)
            
        try:
            # Verify patch content
            if not patch_content or not patch_content.strip():
                logger.error("Empty patch content provided")
                return {
                    "committed": False, 
                    "error": {"code": "EMPTY_PATCH", "message": "No patch content provided"}
                }
                
            # Verify file paths
            if not file_paths or len(file_paths) == 0:
                logger.error("No file paths provided for patch")
                return {
                    "committed": False, 
                    "error": {"code": "NO_FILE_PATHS", "message": "No file paths provided for patch"}
                }
                
            # Parse the patch content to determine what files are being modified
            modified_files = self._parse_patch_files(patch_content, file_paths, branch_name)
            
            # Check if any valid files were found
            if not modified_files:
                logger.error(f"No valid files found in patch")
                return {
                    "committed": False, 
                    "error": {"code": "INVALID_PATCH", "message": "No valid files found in patch"}
                }
                
            # Convert to format expected by commit_changes
            changes = []
            for file_path, content in modified_files.items():
                changes.append({
                    "path": file_path,
                    "content": content
                })
                
            # Log the planned changes
            logger.info(f"Applying patch to {len(changes)} files: {[c['path'] for c in changes]}")
                
            # Commit changes
            return self.commit_changes(branch_name, changes, commit_message)
        except Exception as e:
            logger.error(f"Error applying patch: {str(e)}")
            return {"committed": False, "error": {"code": "PATCH_ERROR", "message": str(e)}}

    # ... keep existing code (_mock_apply_patch)

    def _parse_patch_files(self, patch_content: str, allowed_file_paths: List[str], branch_name: str) -> Dict[str, str]:
        """
        Parse a patch to extract file content using unidiff when available
        """
        logger.info(f"Parsing patch content for files: {allowed_file_paths}")
        
        # If unidiff is available, use it for proper patch parsing
        if unidiff:
            logger.info("Using unidiff for proper patch parsing")
            return self._parse_patch_with_unidiff(patch_content, allowed_file_paths, branch_name)
        else:
            # Fallback to enhanced basic parsing
            logger.warning("unidiff not available - using enhanced basic parsing")
            return self._parse_patch_basic(patch_content, allowed_file_paths, branch_name)
        
    def _parse_patch_with_unidiff(self, patch_content: str, allowed_file_paths: List[str], branch_name: str) -> Dict[str, str]:
        """Parse patch content using unidiff library with intelligent patching"""
        files = {}
        try:
            # Parse the patch using unidiff
            patch_set = unidiff.PatchSet.from_string(patch_content)
            
            # Process each patched file
            for patched_file in patch_set:
                # Extract file path - remove 'a/' and 'b/' prefixes if present
                file_path = patched_file.target_file
                if file_path.startswith('b/'):
                    file_path = file_path[2:]
                
                # Skip files not in allowed_file_paths
                if file_path not in allowed_file_paths:
                    logger.warning(f"File {file_path} not in allowed file paths, skipping")
                    continue
                
                # Get the current content if file exists
                current_content = self._get_file_content(file_path, branch_name)
                logger.info(f"Original content for {file_path}: {len(current_content) if current_content else 0} bytes")
                
                # Apply the patch to the content
                modified_content = self._apply_patched_file(patched_file, current_content)
                logger.info(f"Modified content for {file_path}: {len(modified_content)} bytes")
                
                # Add the modified content to the result
                files[file_path] = modified_content
                logger.info(f"Successfully parsed and applied patch for file: {file_path}")
                
                # Optional: Detailed logging of changes
                lines_original = current_content.splitlines() if current_content else []
                lines_modified = modified_content.splitlines() 
                logger.info(f"Lines in original: {len(lines_original)}, Lines in modified: {len(lines_modified)}")
                
        except Exception as e:
            logger.error(f"Error parsing patch with unidiff: {str(e)}")
            traceback.print_exc()
            logger.warning("Falling back to enhanced basic patch parser")
            return self._parse_patch_basic(patch_content, allowed_file_paths, branch_name)
        
        return files
    
    def _apply_patched_file(self, patched_file, current_content=None):
        """Apply a patched file to current content"""
        if current_content is None or current_content == "":
            logger.info("Creating new file with patch content")
            # For new files, construct the content from added lines only
            lines = []
            for hunk in patched_file:
                for line in hunk:
                    if line.is_added:
                        lines.append(line.value)
            return "\n".join(lines)
        else:
            # Handle patches to existing files
            logger.info("Applying patch to existing content")
            
            # Split content into lines for easier processing
            lines = current_content.splitlines()
            logger.info(f"Starting with {len(lines)} lines of content")
            
            # Track offsets caused by earlier changes
            line_offset = 0
            
            # Process each hunk in the patched file
            for hunk in patched_file:
                source_start = hunk.source_start - 1  # Convert to 0-based index
                source_length = hunk.source_length
                
                # Adjust for offsets from previous hunks
                adjusted_start = source_start + line_offset
                
                # Get lines to remove and lines to add
                removed_lines = [line.value for line in hunk if line.is_removed]
                added_lines = [line.value for line in hunk if line.is_added]
                
                # Log hunk information
                logger.info(f"Hunk: @@ -{source_start+1},{source_length} +{hunk.target_start},{hunk.target_length} @@")
                logger.info(f"  Removing {len(removed_lines)} lines, Adding {len(added_lines)} lines")
                logger.info(f"  Adjusted start line: {adjusted_start}")
                
                # Validation to ensure we're patching at the right place
                if adjusted_start < 0:
                    adjusted_start = 0
                    logger.warning("Adjusted start position to 0")
                    
                if adjusted_start >= len(lines):
                    logger.warning(f"Hunk start position {adjusted_start} beyond end of file ({len(lines)} lines)")
                    adjusted_start = len(lines)
                
                # Remove the specified lines and insert new ones
                if source_length > 0 and len(lines) > 0:
                    # Verify that the removed lines match what we expect
                    actual_lines = lines[adjusted_start:adjusted_start + source_length]
                    expected_lines = [line.value for line in hunk if line.is_removed]
                    
                    # Check if lines match loosely (allowing for slight differences)
                    lines_match = (len(actual_lines) == len(expected_lines))
                    if not lines_match:
                        logger.warning(f"Lines don't match exactly: got {len(actual_lines)}, expected {len(expected_lines)}")
                        
                    # Remove the lines (even if they don't match exactly)
                    del lines[adjusted_start:adjusted_start + source_length]
                
                # Insert the new lines
                for i, line in enumerate(added_lines):
                    if adjusted_start + i <= len(lines):
                        lines.insert(adjusted_start + i, line)
                    else:
                        lines.append(line)
                
                # Update the offset for future hunks
                line_offset += (len(added_lines) - source_length)
                logger.info(f"New line offset: {line_offset}")
            
            logger.info(f"Final content has {len(lines)} lines")
            # Join the lines back into a string
            return '\n'.join(lines)
    
    def _get_file_content(self, file_path, branch_name=None):
        """Get the content of a file from the repository"""
        if not branch_name:
            branch_name = self.default_branch_name
            
        if TEST_MODE:
            # In test mode, check our mock files dict first
            if file_path in self.mock_files:
                logger.info(f"Returning mock content for {file_path}")
                return self.mock_files[file_path]
            
            # Otherwise return mock content
            return f"# Mock content for {file_path}\n# Generated for testing\n\n"
            
        try:
            file_content = self.repo.get_contents(file_path, ref=branch_name)
            content = file_content.decoded_content.decode('utf-8')
            return content
        except Exception as e:
            logger.warning(f"Could not get content for file {file_path}: {str(e)}")
            return ""
        
    def _parse_patch_basic(self, patch_content: str, allowed_file_paths: List[str], branch_name: str) -> Dict[str, str]:
        """Enhanced basic fallback patch parser with better context handling"""
        logger.warning("Using enhanced basic patch parser with context handling")
        files = {}
        
        # First, parse the patch to identify files and hunks
        patch_by_file = {}
        current_file = None
        current_hunks = []
        current_hunk = None
        
        lines = patch_content.splitlines()
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Parse file headers
            if line.startswith('--- a/') and i + 1 < len(lines) and lines[i + 1].startswith('+++ b/'):
                # Save previous file if exists
                if current_file and current_hunks:
                    patch_by_file[current_file] = current_hunks
                
                # Extract new file path
                file_path = lines[i + 1][6:] if lines[i + 1].startswith('+++ b/') else lines[i + 1][4:]
                current_file = file_path
                current_hunks = []
                i += 2  # Skip the +++ line
                continue
            
            # Parse hunk headers
            elif line.startswith('@@') and '@@' in line[2:]:
                # Start a new hunk
                hunk_parts = line.split(' ')
                if len(hunk_parts) >= 3:
                    source_info = hunk_parts[1][1:]  # Remove leading '-'
                    target_info = hunk_parts[2][1:]  # Remove leading '+'
                    
                    # Parse source line info
                    source_parts = source_info.split(',')
                    source_start = int(source_parts[0])
                    source_length = int(source_parts[1]) if len(source_parts) > 1 else 1
                    
                    # Parse target line info
                    target_parts = target_info.split(',')
                    target_start = int(target_parts[0])
                    target_length = int(target_parts[1]) if len(target_parts) > 1 else 1
                    
                    current_hunk = {
                        'source_start': source_start,
                        'source_length': source_length,
                        'target_start': target_start,
                        'target_length': target_length,
                        'context_before': [],
                        'removed': [],
                        'added': [],
                        'context_after': []
                    }
                    current_hunks.append(current_hunk)
                i += 1
                continue
                
            # Parse hunk content
            elif current_hunk is not None:
                if line.startswith('-'):
                    current_hunk['removed'].append(line[1:])
                elif line.startswith('+'):
                    current_hunk['added'].append(line[1:])
                elif line.startswith(' '):  # Context line
                    if len(current_hunk['removed']) == 0 and len(current_hunk['added']) == 0:
                        # Context before any changes
                        current_hunk['context_before'].append(line[1:])
                    else:
                        # Context after changes
                        current_hunk['context_after'].append(line[1:])
                i += 1
                continue
            
            i += 1  # Move to next line
            
        # Save the last file if exists
        if current_file and current_hunks:
            patch_by_file[current_file] = current_hunks
            
        # Log what files were found in the patch
        logger.info(f"Found {len(patch_by_file)} files in patch: {list(patch_by_file.keys())}")
        
        # Now apply the hunks to each file
        for file_path, hunks in patch_by_file.items():
            # Skip files not in our allowed list
            if file_path not in allowed_file_paths:
                logger.warning(f"Skipping file not in allowed list: {file_path}")
                continue
                
            # Get current content of the file
            current_content = self._get_file_content(file_path, branch_name)
            current_lines = current_content.splitlines() if current_content else []
            
            logger.info(f"Applying {len(hunks)} hunks to {file_path} with {len(current_lines)} existing lines")
            
            # Track line offsets as we apply hunks
            line_offset = 0
            
            # Apply each hunk in sequence
            for hunk_index, hunk in enumerate(hunks):
                source_start = hunk['source_start'] - 1  # Convert to 0-based
                source_length = hunk['source_length']
                removed_lines = hunk['removed']
                added_lines = hunk['added']
                context_before = hunk['context_before']
                context_after = hunk['context_after']
                
                # Adjust for previous hunks
                adjusted_start = source_start + line_offset
                
                logger.info(f"Hunk {hunk_index+1}: Line {source_start+1}, {source_length} lines (adjusted: {adjusted_start+1})")
                logger.info(f"  Context before: {len(context_before)} lines")
                logger.info(f"  Removed: {len(removed_lines)} lines")
                logger.info(f"  Added: {len(added_lines)} lines")
                logger.info(f"  Context after: {len(context_after)} lines")
                
                # For new files or empty files, just add the content
                if len(current_lines) == 0:
                    current_lines = context_before + added_lines + context_after
                    logger.info(f"Added {len(current_lines)} lines to new/empty file")
                    continue
                
                # Handle existing files - adjust position if needed
                if adjusted_start < 0:
                    adjusted_start = 0
                    logger.warning(f"Adjusted start position to 0 for hunk {hunk_index+1}")
                elif adjusted_start > len(current_lines):
                    adjusted_start = len(current_lines)
                    logger.warning(f"Adjusted start position to end of file for hunk {hunk_index+1}")
                
                # Remove original lines and insert new ones
                if source_length > 0 and adjusted_start < len(current_lines):
                    # Check how much we can safely remove
                    safe_length = min(source_length, len(current_lines) - adjusted_start)
                    
                    # Remove the lines
                    del current_lines[adjusted_start:adjusted_start + safe_length]
                    logger.info(f"Removed {safe_length} lines at position {adjusted_start+1}")
                
                # Insert the new lines
                for i, line in enumerate(added_lines):
                    current_lines.insert(adjusted_start + i, line)
                    
                logger.info(f"Added {len(added_lines)} lines at position {adjusted_start+1}")
                
                # Update offset for next hunk
                line_offset += (len(added_lines) - source_length)
                logger.info(f"Updated line offset to {line_offset}")
            
            # Join lines back into content
            modified_content = '\n'.join(current_lines)
            if current_content and not modified_content.endswith('\n'):
                modified_content += '\n'
                
            # Store the result
            files[file_path] = modified_content
            logger.info(f"Successfully applied patch to {file_path}: {len(current_lines)} final lines")
            
        return files

    def _mock_create_branch(self, branch_name: str) -> str:
        """Mock implementation of create_branch for testing"""
        logger.info(f"MOCK: Creating branch {branch_name}")
        self.mock_branches.append(branch_name)
        return branch_name

    def _mock_commit_changes(
        self, 
        branch_name: str, 
        changes: List[Dict[str, str]], 
        commit_message: str
    ) -> Dict[str, Any]:
        """Mock implementation of commit_changes for testing"""
        logger.info(f"MOCK: Committing {len(changes)} changes to {branch_name}: {commit_message}")
        
        # Store changes in mock_files
        for change in changes:
            file_path = change.get("path")
            content = change.get("content")
            if file_path and content:
                self.mock_files[file_path] = content
                logger.info(f"MOCK: Updated {file_path} with {len(content)} bytes")
        
        return {"committed": True, "files_changed": len(changes)}

    def _mock_create_pull_request(self, branch_name: str, title: str, description: str) -> str:
        """Mock implementation of create_pull_request for testing"""
        logger.info(f"MOCK: Creating PR for {branch_name}: {title}")
        return f"https://github.com/example/repo/pull/999"

    def _mock_apply_patch(
        self, 
        branch_name: str, 
        patch_content: str, 
        commit_message: str, 
        file_paths: List[str]
    ) -> Dict[str, Any]:
        """Mock implementation of apply_patch for testing"""
        logger.info(f"MOCK: Applying patch to {branch_name}: {len(patch_content)} bytes")
        
        # Parse the patch content
        modified_files = self._parse_patch_files(patch_content, file_paths, branch_name)
        
        # Store modified files
        for file_path, content in modified_files.items():
            self.mock_files[file_path] = content
            logger.info(f"MOCK: Updated {file_path} with patched content: {len(content)} bytes")
            
        return {"committed": True, "files_changed": len(modified_files)}
