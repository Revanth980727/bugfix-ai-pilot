
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
            modified_files = self._parse_patch_files(patch_content, file_paths)
            
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

    def _parse_patch_files(self, patch_content: str, allowed_file_paths: List[str]) -> Dict[str, str]:
        """
        Parse a patch to extract file content using unidiff when available
        """
        logger.info(f"Parsing patch content for files: {allowed_file_paths}")
        
        # If unidiff is available, use it for proper patch parsing
        if unidiff:
            logger.info("Using unidiff for proper patch parsing")
            return self._parse_patch_with_unidiff(patch_content, allowed_file_paths)
        else:
            # Fallback to basic parsing for backward compatibility
            logger.warning("unidiff not available - using basic parsing which may result in incorrect changes")
            return self._parse_patch_basic(patch_content, allowed_file_paths)
        
    def _parse_patch_with_unidiff(self, patch_content: str, allowed_file_paths: List[str]) -> Dict[str, str]:
        """Parse patch content using unidiff library"""
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
                current_content = self._get_file_content(file_path, branch_name=self.default_branch_name)
                
                # Apply the patch to the content
                modified_content = self._apply_patched_file(patched_file, current_content)
                
                # Add the modified content to the result
                files[file_path] = modified_content
                logger.info(f"Successfully parsed and applied patch for file: {file_path}")
                
        except Exception as e:
            logger.error(f"Error parsing patch with unidiff: {str(e)}")
            traceback.print_exc()
            logger.warning("Falling back to basic patch parser")
            return self._parse_patch_basic(patch_content, allowed_file_paths)
        
        return files
    
    def _apply_patched_file(self, patched_file, current_content=None):
        """Apply a patched file to current content"""
        if current_content is None:
            current_content = ""
            
        # Split content into lines for easier processing
        lines = current_content.splitlines()
        
        # Process each hunk in the patched file
        for hunk in patched_file:
            source_start = hunk.source_start - 1  # Convert to 0-based index
            source_length = hunk.source_length
            target_start = hunk.target_start - 1  # Convert to 0-based index
            target_length = hunk.target_length
            
            # Get lines to remove and lines to add
            removed_lines = [line.value for line in hunk if line.is_removed]
            added_lines = [line.value for line in hunk if line.is_added]
            
            # Apply the changes to the lines
            if source_length > 0:
                # Remove the specified lines
                lines[source_start:source_start + source_length] = []
                
            # Insert the new lines
            for i, line in enumerate(added_lines):
                lines.insert(source_start + i, line)
        
        # Join the lines back into a string
        return '\n'.join(lines) + '\n'
    
    def _get_file_content(self, file_path, branch_name=None):
        """Get the content of a file from the repository"""
        if not branch_name:
            branch_name = self.default_branch_name
            
        if TEST_MODE:
            # Mock file content
            return f"# Mock content for {file_path}\n# Generated for testing\n\n"
            
        try:
            file_content = self.repo.get_contents(file_path, ref=branch_name)
            return file_content.decoded_content.decode('utf-8')
        except Exception as e:
            logger.warning(f"Could not get content for file {file_path}: {str(e)}")
            return ""
        
    def _parse_patch_basic(self, patch_content: str, allowed_file_paths: List[str]) -> Dict[str, str]:
        """Improved basic fallback patch parser when unidiff is not available"""
        logger.warning("Using basic patch parser - working with limited patch parsing capabilities")
        files = {}
        current_file = None
        hunk_info = {}
        
        # First, identify all the files and their hunks
        lines = patch_content.splitlines()
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Detect file headers
            if line.startswith('--- a/') and i + 1 < len(lines) and lines[i + 1].startswith('+++ b/'):
                # Extract file path from the +++ line
                file_path = lines[i + 1][6:]  # Remove '+++ b/' prefix
                current_file = file_path
                
                # Initialize hunk info for this file
                if current_file not in hunk_info:
                    hunk_info[current_file] = []
                
                # Skip the +++ line
                i += 2
                continue
            
            # Process hunk headers
            elif line.startswith('@@') and '@@' in line[2:]:
                if current_file:
                    # Parse hunk header to get line numbers
                    # Format is typically @@ -l,s +l,s @@ optional section heading
                    header_parts = line.split(' ')
                    if len(header_parts) >= 3:
                        source_info = header_parts[1]  # -l,s part
                        target_info = header_parts[2]  # +l,s part
                        
                        # Parse source (original file) info
                        if source_info.startswith('-'):
                            source_parts = source_info[1:].split(',')
                            source_start = int(source_parts[0])
                            source_length = int(source_parts[1]) if len(source_parts) > 1 else 1
                        else:
                            source_start = 0
                            source_length = 0
                        
                        # Parse target (new file) info
                        if target_info.startswith('+'):
                            target_parts = target_info[1:].split(',')
                            target_start = int(target_parts[0])
                            target_length = int(target_parts[1]) if len(target_parts) > 1 else 1
                        else:
                            target_start = 0
                            target_length = 0
                        
                        # Store hunk information
                        current_hunk = {
                            'source_start': source_start,
                            'source_length': source_length,
                            'target_start': target_start,
                            'target_length': target_length,
                            'content': [line],  # Start with the header line
                            'removed_lines': [],
                            'added_lines': []
                        }
                        
                        hunk_info[current_file].append(current_hunk)
                    else:
                        logger.warning(f"Malformed hunk header: {line}")
                else:
                    logger.warning(f"Found hunk header without file: {line}")
            
            # Process content lines
            elif current_file and hunk_info.get(current_file):
                current_hunk = hunk_info[current_file][-1]
                current_hunk['content'].append(line)
                
                if line.startswith('-'):
                    current_hunk['removed_lines'].append(line[1:])
                elif line.startswith('+'):
                    current_hunk['added_lines'].append(line[1:])
                    
            i += 1
        
        # Now, fetch current content and apply patches for each file
        for file_path, hunks in hunk_info.items():
            if file_path in allowed_file_paths:
                # Get current content
                current_content = self._get_file_content(file_path)
                content_lines = current_content.splitlines() if current_content else []
                
                # Apply each hunk
                offsets = {}  # Track line shifts due to previous hunks
                
                for hunk in hunks:
                    source_start = hunk['source_start'] - 1  # Convert to 0-based
                    source_length = hunk['source_length']
                    added_lines = hunk['added_lines']
                    
                    # Adjust for previous changes
                    source_start_adjusted = source_start
                    if source_start in offsets:
                        source_start_adjusted += offsets[source_start]
                    
                    # Remove the original lines
                    if source_start_adjusted < len(content_lines) and source_length > 0:
                        content_lines[source_start_adjusted:source_start_adjusted + source_length] = []
                    
                    # Add the new lines
                    for i, line in enumerate(added_lines):
                        if source_start_adjusted + i <= len(content_lines):
                            content_lines.insert(source_start_adjusted + i, line)
                        else:
                            content_lines.append(line)
                    
                    # Update offsets for future hunks
                    line_diff = len(added_lines) - source_length
                    for line_num in sorted(list(offsets.keys())):
                        if line_num > source_start:
                            offsets[line_num] += line_diff
                    
                    # Add offset for this hunk
                    offsets[source_start] = offsets.get(source_start, 0) + line_diff
                
                # Join back into content
                files[file_path] = '\n'.join(content_lines) + '\n'
                logger.info(f"Applied changes to {file_path} using basic parser")
        
        return files
