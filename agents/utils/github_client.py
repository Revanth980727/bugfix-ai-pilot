
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
        if not branch:
            branch = self.default_branch
            
        url = f"{self.repo_api_url}/contents/{file_path}?ref={branch}"
        
        self.logger.info(f"Fetching content of {file_path} from {branch}")
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            self.logger.error(f"Failed to get {file_path}: {response.status_code}, {response.text}")
            response.raise_for_status()
            
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        
        return content, data["sha"]
        
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
        if not branch:
            branch = self.default_branch
            
        # Get SHA if not provided
        if not sha:
            try:
                _, sha = self.get_file_contents(file_path, branch)
            except Exception as e:
                self.logger.error(f"Failed to get SHA for {file_path}: {str(e)}")
                return False
        
        url = f"{self.repo_api_url}/contents/{file_path}"
        
        payload = {
            "message": commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "sha": sha,
            "branch": branch
        }
        
        self.logger.info(f"Updating {file_path} on branch {branch}")
        response = requests.put(url, headers=self.headers, json=payload)
        
        if response.status_code not in (200, 201):
            self.logger.error(f"Failed to update {file_path}: {response.status_code}, {response.text}")
            return False
            
        self.logger.info(f"Successfully updated {file_path} on branch {branch}")
        return True
        
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
            self.logger.error(f"Failed to create PR: {response.status_code}, {response.text}")
            return None
            
        pr_url = response.json()["html_url"]
        self.logger.info(f"Successfully created PR: {pr_url}")
        return pr_url
        
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
        # This is a simplified implementation - in a real scenario
        # you'd need to parse the patch and apply it correctly to each file
        
        for file_path in patch_file_paths:
            try:
                # Get current content
                current_content, sha = self.get_file_contents(file_path, branch_name)
                
                # Apply patch (simplified - this would need proper diff application)
                # In a real implementation, use a proper patch library
                new_content = current_content  # This should be patched content
                
                # Update file
                success = self.update_file(
                    file_path=file_path,
                    content=new_content,
                    commit_message=commit_message,
                    branch=branch_name,
                    sha=sha
                )
                
                if not success:
                    self.logger.error(f"Failed to update {file_path}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error applying patch to {file_path}: {str(e)}")
                return False
                
        return True
