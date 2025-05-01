
import os
import base64
import requests
from typing import Dict, Any, List, Optional, Tuple
from .logger import Logger

class GitHubClient:
    """Client for interacting with the GitHub API"""
    
    def __init__(self):
        """Initialize GitHub client with environment variables"""
        self.logger = Logger("github_client")
        
        # Get credentials from environment variables
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.repo_owner = os.environ.get("GITHUB_REPO_OWNER")
        self.repo_name = os.environ.get("GITHUB_REPO_NAME")
        self.default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
        
        if not all([self.github_token, self.repo_owner, self.repo_name]):
            self.logger.error("Missing required GitHub environment variables")
            raise EnvironmentError(
                "Missing GitHub credentials. Please set GITHUB_TOKEN, GITHUB_REPO_OWNER and GITHUB_REPO_NAME environment variables."
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
        
    def get_file_contents(self, file_path: str, branch: str = None) -> Tuple[str, str]:
        """
        Get file contents and sha from GitHub
        
        Args:
            file_path: Path to the file in the repository
            branch: Branch name (defaults to default_branch if not specified)
            
        Returns:
            Tuple containing (content, sha)
        """
        # ... keep existing code (file content retrieval logic)
        
    def check_branch_exists(self, branch_name: str) -> bool:
        """
        Check if a branch exists in the repository
        
        Args:
            branch_name: Name of the branch to check
            
        Returns:
            bool: True if the branch exists, False otherwise
        """
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
        
    def update_file(self, file_path: str, content: str, commit_message: str, branch: str = None, sha: str = None) -> bool:
        """
        Update a file in GitHub repository
        
        Args:
            file_path: Path to the file in the repository
            content: New content for the file
            commit_message: Commit message
            branch: Branch name (defaults to default_branch if not specified)
            sha: SHA of the file (if not provided, will be fetched)
            
        Returns:
            Success status (True/False)
        """
        # ... keep existing code (file update logic)
        
    def create_branch(self, branch_name: str, from_branch: str = None) -> bool:
        """
        Create a new branch in the repository
        
        Args:
            branch_name: Name for the new branch
            from_branch: Base branch name (defaults to default_branch if not specified)
            
        Returns:
            Success status (True/False)
        """
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
        
    def create_pull_request(self, title: str, body: str, head_branch: str, base_branch: str = None) -> Optional[str]:
        """
        Create a pull request
        
        Args:
            title: PR title
            body: PR description
            head_branch: Source branch
            base_branch: Target branch (defaults to default_branch if not specified)
            
        Returns:
            PR URL if successful, None otherwise
        """
        if not base_branch:
            base_branch = self.default_branch
            
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
                    self.logger.info(f"Found existing PR: {pr_url}")
                    return pr_url
                    
                return None
            
            self.logger.error(f"Failed to create PR: {response.status_code}, {response.text}")
            return None
            
        pr_url = response.json()["html_url"]
        pr_number = response.json()["number"]
        self.logger.info(f"Successfully created PR #{pr_number}: {pr_url}")
        return pr_url
       
    def add_pr_comment(self, pr_number: str, comment: str) -> bool:
        """
        Add a comment to a pull request
        
        Args:
            pr_number: Pull request number (or PR object)
            comment: Comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Validate PR number
        if not pr_number:
            self.logger.error("Invalid PR number: None")
            return False
        
        # Handle different PR number formats
        try:
            # Convert to string if it's not already
            pr_number_str = str(pr_number)
            
            # Try to handle PR URLs
            if pr_number_str.startswith('http'):
                import re
                pr_match = re.search(r'/pull/(\d+)', pr_number_str)
                if pr_match:
                    pr_number_str = pr_match.group(1)
                else:
                    self.logger.error(f"Could not extract PR number from URL: {pr_number_str}")
                    return False
            
            # Ensure it's a numeric value
            if not pr_number_str.isdigit():
                self.logger.error(f"Invalid PR number format: {pr_number_str}")
                return False
                
            url = f"{self.repo_api_url}/issues/{pr_number_str}/comments"
            
            payload = {"body": comment}
            
            self.logger.info(f"Adding comment to PR #{pr_number_str}")
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code != 201:
                self.logger.error(f"Failed to add comment to PR #{pr_number_str}: {response.status_code}, {response.text}")
                return False
                
            self.logger.info(f"Successfully added comment to PR #{pr_number_str}")
            return True
            
        except Exception as e:
            self.logger.error(f"Unexpected error adding comment to PR #{pr_number}: {str(e)}")
            return False
        
    def commit_patch(self, branch_name: str, patch_content: str, commit_message: str, 
                    patch_file_paths: List[str]) -> bool:
        """
        Apply a patch to specified files and commit changes
        
        Args:
            branch_name: Branch to commit to
            patch_content: Unified diff/patch content
            commit_message: Commit message
            patch_file_paths: List of files that are modified in the patch
            
        Returns:
            Success status (True/False)
        """
        # ... keep existing code (patch application logic)

