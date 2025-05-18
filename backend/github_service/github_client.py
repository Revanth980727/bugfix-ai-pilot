
import os
import base64
import json
import requests
from typing import Dict, Any, List, Optional, Tuple, Union
import logging

class GitHubClient:
    """Client for interacting with the GitHub API"""
    
    def __init__(self, force_real=False):
        """Initialize GitHub client with environment variables"""
        self.logger = logging.getLogger("github-client")
        
        # Get credentials from environment variables
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.repo_owner = os.environ.get("GITHUB_REPO_OWNER")
        self.repo_name = os.environ.get("GITHUB_REPO_NAME")
        self.default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
        self.use_default_branch_only = os.environ.get("GITHUB_USE_DEFAULT_BRANCH_ONLY", "False").lower() == "true"
        
        # Check for test mode
        self.test_mode = os.environ.get("TEST_MODE", "False").lower() == "true"
        
        # If force_real is True, we should not use test mode regardless of env setting
        if force_real:
            self.test_mode = False
            self.logger.info("Forcing real GitHub interaction (test mode disabled)")
        
        # Validate configuration before proceeding
        if not all([self.github_token, self.repo_owner, self.repo_name]):
            self.logger.error("Missing required GitHub environment variables")
            error_details = {
                "token_present": bool(self.github_token),
                "owner_present": bool(self.repo_owner),
                "repo_present": bool(self.repo_name)
            }
            self.logger.error(f"Configuration details: {error_details}")
            
            if not self.test_mode:
                raise EnvironmentError(
                    "Missing GitHub credentials. Please set GITHUB_TOKEN, GITHUB_REPO_OWNER and GITHUB_REPO_NAME environment variables."
                )
            else:
                self.logger.warning("⚠️ Running in TEST_MODE with incomplete GitHub configuration!")
        
        # Check for placeholder values
        placeholder_found = False
        if self.github_token == "your_github_token_here":
            self.logger.error("GITHUB_TOKEN contains a placeholder value")
            placeholder_found = True
            
        if self.repo_owner == "your_github_username_or_org":
            self.logger.error("GITHUB_REPO_OWNER contains a placeholder value")
            placeholder_found = True
            
        if self.repo_name == "your_repository_name":
            self.logger.error("GITHUB_REPO_NAME contains a placeholder value")
            placeholder_found = True
            
        # Fail on placeholder values if not in test mode
        if placeholder_found and not self.test_mode:
            raise ValueError(
                "GitHub configuration contains placeholder values. Please set valid values in your .env file."
            )
            
        # Set up headers
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.github_token}",
            "Content-Type": "application/json"
        }
        
        # API base URL
        self.base_url = "https://api.github.com"
        self.repo_api_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        
        # Log configuration
        self.logger.info(f"GitHub client initialized with repo {self.repo_owner}/{self.repo_name}")
        self.logger.info(f"Default branch: {self.default_branch}")
        self.logger.info(f"Use default branch only: {self.use_default_branch_only}")
        
        if self.test_mode:
            self.logger.warning("⚠️ Running in TEST_MODE - all GitHub operations will be simulated!")
        
    def check_branch_exists(self, branch_name: str) -> bool:
        """
        Check if a branch exists in the repository
        
        Args:
            branch_name: Name of the branch to check
            
        Returns:
            bool: True if the branch exists, False otherwise
        """
        # In test mode, simulate success
        if self.test_mode:
            self.logger.info(f"[TEST MODE] Simulating branch check for {branch_name}")
            return True
            
        url = f"{self.repo_api_url}/git/refs/heads/{branch_name}"
        
        self.logger.info(f"Checking if branch {branch_name} exists")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            self.logger.info(f"Branch {branch_name} exists")
            return True
        elif response.status_code == 404:
            self.logger.info(f"Branch {branch_name} does not exist")
            return False
        else:
            self.logger.error(f"Failed to check if branch {branch_name} exists: {response.status_code}, {response.text}")
            # Assume it doesn't exist to be safe
            return False
        
    def create_branch(self, branch_name: str, from_branch: str = None) -> bool:
        """
        Create a new branch in the repository
        
        Args:
            branch_name: Name for the new branch
            from_branch: Base branch name (defaults to default_branch if not specified)
            
        Returns:
            Success status (True/False)
        """
        # Check if we should only use the default branch
        if self.use_default_branch_only:
            self.logger.info(f"Skipping branch creation for {branch_name} - configured to use default branch only ({self.default_branch})")
            return True
            
        # In test mode, simulate success
        if self.test_mode:
            self.logger.info(f"[TEST MODE] Simulating branch creation: {branch_name}")
            return True
        
        if not from_branch:
            from_branch = self.default_branch
            
        # Check if the branch already exists first
        if self.check_branch_exists(branch_name):
            self.logger.warning(f"Branch {branch_name} already exists")
            return True
            
        # Get the latest commit SHA from the base branch
        url = f"{self.repo_api_url}/git/refs/heads/{from_branch}"
        
        self.logger.info(f"Getting latest commit from {from_branch}")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            self.logger.error(f"Failed to get commit SHA for {from_branch}: {response.status_code}")
            return False
            
        sha = response.json()["object"]["sha"]
        
        # Create the new branch
        create_url = f"{self.repo_api_url}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": sha
        }
        
        self.logger.info(f"Creating branch {branch_name} from {from_branch}")
        create_response = requests.post(create_url, headers=self.headers, json=payload)
        
        # Handle case where branch might already exist
        if create_response.status_code == 422:
            self.logger.warning(f"Branch {branch_name} already exists")
            return True
            
        if create_response.status_code != 201:
            self.logger.error(f"Failed to create branch {branch_name}: {create_response.status_code}, {create_response.text}")
            return False
            
        self.logger.info(f"Successfully created branch {branch_name}")
        return True
        
    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = None) -> Tuple[str, int]:
        """
        Create a pull request
        
        Args:
            title: PR title
            body: PR description
            head_branch: Source branch
            base_branch: Target branch (defaults to default_branch if not specified)
            
        Returns:
            Tuple of (PR URL, PR number) if successful
        """
        if not base_branch:
            base_branch = self.default_branch
        
        # If we're configured to only use the default branch, set the head branch to it as well
        if self.use_default_branch_only:
            self.logger.info(f"Using default branch {self.default_branch} as head branch instead of {head_branch}")
            head_branch = self.default_branch
            
        # If in test mode, return a mock PR URL and PR number
        if self.test_mode:
            self.logger.warning("⚠️ TEST MODE: Creating mock PR instead of real GitHub PR")
            mock_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/pull/999"
            mock_pr_number = 999
            return mock_url, mock_pr_number
            
        # Only create a mock PR if configured to use only default branch (no need for real PR)
        if self.use_default_branch_only:
            self.logger.info("Skipping PR creation since we're only using the default branch")
            return f"https://github.com/{self.repo_owner}/{self.repo_name}/tree/{self.default_branch}", 0
            
        url = f"{self.repo_api_url}/pulls"
        
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": False
        }
        
        self.logger.info(f"Creating PR from {head_branch} to {base_branch}")
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code != 201:
            # Check if it's because the PR already exists
            if response.status_code == 422 and "A pull request already exists" in response.text:
                self.logger.info(f"PR from {head_branch} to {base_branch} already exists")
                
                # Try to get the URL of the existing PR
                existing_prs = requests.get(
                    f"{self.repo_api_url}/pulls?head={self.repo_owner}:{head_branch}&base={base_branch}&state=open",
                    headers=self.headers
                )
                
                if existing_prs.status_code == 200 and existing_prs.json():
                    pr_url = existing_prs.json()[0]["html_url"]
                    pr_number = existing_prs.json()[0]["number"]
                    self.logger.info(f"Found existing PR: {pr_url} (#{pr_number})")
                    return pr_url, pr_number
                    
                return "", 0  # Return empty strings instead of None
            
            self.logger.error(f"Failed to create PR: {response.status_code}, {response.text}")
            return "", 0  # Return empty strings instead of None
            
        pr_url = response.json()["html_url"]
        pr_number = response.json()["number"]
        self.logger.info(f"Successfully created PR #{pr_number}: {pr_url}")
        return pr_url, pr_number
        
    def commit_file(self, branch_name: str, file_path: str, content: str, commit_message: str) -> bool:
        """
        Commit a file to the repository
        
        Args:
            file_path: Path to the file in the repository
            content: New content for the file
            commit_message: Commit message
            branch_name: Branch to commit to
            
        Returns:
            Success status (True/False)
        """
        # In test mode, simulate success
        if self.test_mode:
            self.logger.warning(f"[TEST MODE] Simulating file commit for {file_path} to branch {branch_name}")
            return True

        # Type safety: ensure content is a string before encoding
        if not isinstance(content, str):
            if isinstance(content, dict):
                self.logger.warning(f"Converting dict content to JSON string for file {file_path}")
                content = json.dumps(content, indent=2)
            else:
                try:
                    self.logger.warning(f"Converting {type(content).__name__} to string for file {file_path}")
                    content = str(content)
                except Exception as e:
                    self.logger.error(f"Cannot convert content to string for {file_path}: {str(e)}")
                    return False
        
        # First, get the current file info to get the SHA
        url = f"{self.repo_api_url}/contents/{file_path}"
        params = {"ref": branch_name}
        
        self.logger.info(f"Checking if file {file_path} exists in {branch_name}")
        response = requests.get(url, headers=self.headers, params=params)
        
        try:
            if response.status_code == 200:
                # File exists, update it
                file_sha = response.json()["sha"]
                
                update_data = {
                    "message": commit_message,
                    "content": base64.b64encode(content.encode('utf-8')).decode(),
                    "sha": file_sha,
                    "branch": branch_name
                }
                
                self.logger.info(f"Updating existing file {file_path} in {branch_name}")
                update_response = requests.put(url, headers=self.headers, json=update_data)
                
                if update_response.status_code != 200:
                    self.logger.error(f"Failed to update file {file_path}: {update_response.status_code}, {update_response.text}")
                    return False
                    
                self.logger.info(f"Successfully updated file {file_path}")
                return True
            elif response.status_code == 404:
                # File doesn't exist, create it
                create_data = {
                    "message": commit_message,
                    "content": base64.b64encode(content.encode('utf-8')).decode(),
                    "branch": branch_name
                }
                
                self.logger.info(f"Creating new file {file_path} in {branch_name}")
                create_response = requests.put(url, headers=self.headers, json=create_data)
                
                if create_response.status_code != 201:
                    self.logger.error(f"Failed to create file {file_path}: {create_response.status_code}, {create_response.text}")
                    return False
                    
                self.logger.info(f"Successfully created file {file_path}")
                return True
            else:
                self.logger.error(f"Failed to check file {file_path}: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error in commit_file for {file_path}: {str(e)}")
            return False

    def get_file_content(self, file_path: str, branch: str = None) -> Optional[str]:
        """
        Get the content of a file from GitHub
        
        Args:
            file_path: Path to the file in the repository
            branch: Branch to retrieve from (defaults to default_branch)
            
        Returns:
            The content of the file if successful, None otherwise
        """
        # In test mode, return mock content
        if self.test_mode:
            self.logger.warning(f"[TEST MODE] Returning mock content for file {file_path}")
            return f"// Mock content for {file_path} (TEST_MODE is enabled)\n// Set TEST_MODE=False in .env for real GitHub interactions"
            
        if not branch:
            branch = self.default_branch
            
        url = f"{self.repo_api_url}/contents/{file_path}"
        params = {"ref": branch}
        
        self.logger.info(f"Fetching file content: {file_path} from branch {branch}")
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code != 200:
            self.logger.error(f"Failed to fetch file {file_path}: {response.status_code}")
            return None
            
        content_data = response.json()
        if content_data.get("type") != "file":
            self.logger.error(f"Path {file_path} is not a file")
            return None
            
        try:
            content = base64.b64decode(content_data["content"]).decode("utf-8")
            self.logger.info(f"Successfully fetched file content: {file_path}")
            return content
        except Exception as e:
            self.logger.error(f"Failed to decode file content: {str(e)}")
            return None

    # Add a method to check if branches have differences
    def check_branches_have_diff(self, head_branch: str, base_branch: str = None) -> bool:
        """
        Check if there are differences between two branches
        
        Args:
            head_branch: Source branch
            base_branch: Target branch (defaults to default_branch)
            
        Returns:
            True if differences exist, False otherwise
        """
        if self.test_mode:
            self.logger.warning(f"[TEST MODE] Simulating branch diff check between {head_branch} and {base_branch or self.default_branch}")
            return True
            
        if not base_branch:
            base_branch = self.default_branch
            
        # If using only default branch, there are no diffs
        if self.use_default_branch_only and head_branch == base_branch:
            self.logger.info(f"No diffs when comparing the same branch {head_branch}")
            return False
            
        url = f"{self.repo_api_url}/compare/{base_branch}...{head_branch}"
        
        self.logger.info(f"Checking for differences between {base_branch} and {head_branch}")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            self.logger.error(f"Failed to compare branches: {response.status_code}, {response.text}")
            return False
            
        compare_data = response.json()
        has_commits = compare_data.get("total_commits", 0) > 0
        has_files = len(compare_data.get("files", [])) > 0
        
        if has_commits and has_files:
            self.logger.info(f"Found differences between {base_branch} and {head_branch}: {compare_data.get('total_commits')} commits, {len(compare_data.get('files', []))} files")
            return True
        else:
            self.logger.warning(f"No meaningful differences found between {base_branch} and {head_branch}")
            return False
