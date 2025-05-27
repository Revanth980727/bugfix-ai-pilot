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

# Import the patch engine
try:
    from github_service.patch_engine import apply_patch_to_content, validate_patch
except ImportError:
    logging.error("Failed to import patch_engine - check if file exists")
    try:
        from .patch_engine import apply_patch_to_content, validate_patch
        logging.info("Successfully imported patch_engine using relative import")
    except ImportError:
        logging.critical("Could not import patch_engine module")
        
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
        file_paths: List[str],
        expected_content: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Apply a patch to the repository"""
        if TEST_MODE:
            return self._mock_apply_patch(branch_name, patch_content, commit_message, file_paths, expected_content)
            
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
            # Use our improved patch engine to handle this
            modified_files = self._parse_patch_files(patch_content, file_paths, branch_name, expected_content)
            
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

    def _parse_patch_files(
        self, 
        patch_content: str, 
        allowed_file_paths: List[str], 
        branch_name: str,
        expected_content: Dict[str, str] = None
    ) -> Dict[str, str]:
        """
        Parse a patch and apply it to files using our layered patch engine
        """
        logger.info(f"Parsing and applying patch for files: {allowed_file_paths}")
        
        results = {}
        
        # Process each file path
        for file_path in allowed_file_paths:
            if file_path not in results:
                # Get the current content of the file
                original_content = self._get_file_content(file_path, branch_name)
                
                # Apply the patch to the file using our layered patch engine
                success, patched_content, method = apply_patch_to_content(
                    original_content=original_content,
                    patch_content=patch_content,
                    file_path=file_path,
                    expected_content=expected_content.get(file_path) if expected_content else None
                )
                
                # If the patch was applied successfully, add it to the results
                if success:
                    results[file_path] = patched_content
                    logger.info(f"Successfully applied patch to {file_path} using {method}")
                else:
                    logger.warning(f"Failed to apply patch to {file_path}")
        
        # If expected_content is provided, validate the results match
        if expected_content:
            # Use the validate_patch function to verify results
            validation_result = validate_patch(
                patch_content=patch_content,
                file_paths=allowed_file_paths,
                original_contents={path: self._get_file_content(path, branch_name) for path in allowed_file_paths},
                expected_contents=expected_content
            )
            
            logger.info(f"Patch validation result: valid={validation_result['valid']}")
            
            # Add any files that were validated but not patched
            for file_path, file_result in validation_result.get('file_results', {}).items():
                if file_result.get('valid') and file_path not in results and file_path in expected_content:
                    # If the file was validated but not patched, add the expected content as fallback
                    results[file_path] = expected_content[file_path]
                    logger.info(f"Added {file_path} from expected content as fallback")
        
        return results
        
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
        file_paths: List[str],
        expected_content: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Mock implementation of apply_patch for testing"""
        logger.info(f"MOCK: Applying patch to {branch_name}: {len(patch_content)} bytes")
        
        # Parse the patch content using our new method
        modified_files = self._parse_patch_files(patch_content, file_paths, branch_name, expected_content)
        
        # Store modified files
        for file_path, content in modified_files.items():
            self.mock_files[file_path] = content
            logger.info(f"MOCK: Updated {file_path} with patched content: {len(content)} bytes")
            
        return {"committed": True, "files_changed": len(modified_files)}
