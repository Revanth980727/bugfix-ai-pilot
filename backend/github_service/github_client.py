
import os
import sys
import logging
import traceback
from typing import Dict, List, Any, Union, Optional
from datetime import datetime

# Try to import PyGithub
try:
    from github import Github, GithubException, UnknownObjectException
    from github.Repository import Repository
    from github.Branch import Branch
    from github.ContentFile import ContentFile
except ImportError:
    logging.error("Failed to import PyGithub - make sure it's installed")
    raise

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

    def _mock_create_branch(self, branch_name: str) -> str:
        """Mock implementation of create_branch"""
        # Check if branch exists in mock data
        if branch_name in self.mock_branches:
            logger.info(f"Mock: Branch {branch_name} already exists")
            return branch_name
            
        # Add branch to mock data
        self.mock_branches.append(branch_name)
        logger.info(f"Mock: Created branch {branch_name}")
        
        return branch_name

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

    def _mock_commit_changes(
        self, 
        branch_name: str, 
        changes: List[Dict[str, str]], 
        commit_message: str
    ) -> Dict[str, Any]:
        """Mock implementation of commit_changes"""
        # Check if branch exists
        if branch_name not in self.mock_branches:
            logger.error(f"Mock: Branch {branch_name} does not exist")
            return {"committed": False, "error": {"code": "BRANCH_NOT_FOUND", "message": f"Branch {branch_name} not found"}}
            
        # Track changes
        files_changed = 0
        
        # Process each file change
        for change in changes:
            file_path = change.get("path")
            content = change.get("content")
            
            if not file_path or not content:
                continue
                
            # Store in mock data
            if branch_name not in self.mock_files:
                self.mock_files[branch_name] = {}
                
            # Check if file exists and content is different
            existing_content = self.mock_files[branch_name].get(file_path)
            if existing_content != content:
                self.mock_files[branch_name][file_path] = content
                files_changed += 1
                
        # Return result
        if files_changed > 0:
            logger.info(f"Mock: Committed {files_changed} files to {branch_name}")
            return {"committed": True, "files_changed": files_changed}
        else:
            logger.warning(f"Mock: No files were changed in this commit")
            return {
                "committed": False, 
                "error": {"code": "EMPTY_COMMIT", "message": "No files were changed in this commit"}
            }

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

    def _mock_create_pull_request(self, branch_name: str, title: str, description: str) -> str:
        """Mock implementation of create_pull_request"""
        # Check if branch exists
        if branch_name not in self.mock_branches:
            logger.error(f"Mock: Branch {branch_name} does not exist")
            return ""
            
        # Generate mock PR URL
        pr_number = int(datetime.now().timestamp()) % 1000  # Generate a "unique" number
        pr_url = f"https://github.com/{GITHUB_REPO_OWNER or 'example-org'}/{GITHUB_REPO_NAME or 'example-repo'}/pull/{pr_number}"
        
        logger.info(f"Mock: Created PR: {pr_url}")
        return pr_url

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
            # This would typically use Git's patch application functionality
            # For simplicity in this example, we'll extract content from the patch
            # and update files individually
            
            # Parse the patch content to determine what files are being modified
            modified_files = self._parse_patch_files(patch_content)
            
            # Check if any valid files were found
            if not modified_files:
                logger.error(f"No valid files found in patch")
                return {
                    "committed": False, 
                    "error": {"code": "INVALID_PATCH", "message": "No valid files found in patch"}
                }
                
            # Filter files to only those in file_paths
            filtered_files = {}
            for file_path, content in modified_files.items():
                if file_path in file_paths:
                    filtered_files[file_path] = content
                else:
                    logger.warning(f"File {file_path} not in allowed file_paths, ignoring")
                    
            # Check if any files remain after filtering
            if not filtered_files:
                logger.error(f"No files from file_paths found in patch")
                return {
                    "committed": False, 
                    "error": {"code": "NO_MATCHING_FILES", "message": "No files from file_paths found in patch"}
                }
                
            # Convert to format expected by commit_changes
            changes = []
            for file_path, content in filtered_files.items():
                changes.append({
                    "path": file_path,
                    "content": content
                })
                
            # Commit changes
            return self.commit_changes(branch_name, changes, commit_message)
        except Exception as e:
            logger.error(f"Error applying patch: {str(e)}")
            return {"committed": False, "error": {"code": "PATCH_ERROR", "message": str(e)}}

    def _mock_apply_patch(
        self, 
        branch_name: str, 
        patch_content: str, 
        commit_message: str, 
        file_paths: List[str]
    ) -> Dict[str, Any]:
        """Mock implementation of apply_patch"""
        # Simulate parsing the patch content
        mock_changes = []
        
        # Create a mock change for each file path
        for file_path in file_paths:
            mock_changes.append({
                "path": file_path,
                "content": f"Mock content for {file_path}\nPatched at {datetime.now()}\n\n{patch_content[:50]}...\n"
            })
            
        # Use the mock commit changes function
        return self._mock_commit_changes(branch_name, mock_changes, commit_message)

    def _parse_patch_files(self, patch_content: str) -> Dict[str, str]:
        """
        Parse a patch to extract file content
        This is a simplification - real implementation would use git apply
        """
        # For this example, we'll just extract file names from the patch
        # and generate placeholder content
        # In a real implementation, you'd parse the unified diff properly
        
        files = {}
        current_file = None
        
        for line in patch_content.splitlines():
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                # Extract file path
                file_path = line[6:]  # Remove '+++ b/' or '--- a/'
                
                if line.startswith('+++ b/'):
                    current_file = file_path
                    files[current_file] = f"# Generated from patch\n# {datetime.now()}\n\n"
            
            elif current_file and line.startswith('+') and not line.startswith('+++'):
                # Add content from added lines
                content_line = line[1:]  # Remove the '+' prefix
                files[current_file] += content_line + '\n'
                
        return files
