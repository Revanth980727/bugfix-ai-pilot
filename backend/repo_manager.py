
import os
import subprocess
import logging
import shutil
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger("repo-manager")

class RepositoryManager:
    """Manages cloning and accessing the GitHub repository"""
    
    def __init__(self):
        self.repo_path = os.environ.get("REPO_PATH", "/app/code_repo")
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_owner = os.environ.get("GITHUB_REPO_OWNER")
        self.github_repo = os.environ.get("GITHUB_REPO_NAME")
        self.github_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
        
    def clone_repository(self) -> bool:
        """Clone the repository if it doesn't exist"""
        try:
            if os.path.exists(self.repo_path):
                logger.info(f"Repository already exists at {self.repo_path}")
                return self._update_repository()
            
            # Create the directory
            os.makedirs(os.path.dirname(self.repo_path), exist_ok=True)
            
            # Build clone URL with token
            clone_url = f"https://{self.github_token}@github.com/{self.github_owner}/{self.github_repo}.git"
            
            logger.info(f"Cloning repository {self.github_owner}/{self.github_repo} to {self.repo_path}")
            
            result = subprocess.run([
                "git", "clone", "--branch", self.github_branch, 
                clone_url, self.repo_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Repository cloned successfully")
                return True
            else:
                logger.error(f"Failed to clone repository: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error cloning repository: {str(e)}")
            return False
    
    def _update_repository(self) -> bool:
        """Pull latest changes from the repository"""
        try:
            logger.info("Updating repository with latest changes")
            result = subprocess.run([
                "git", "pull", "origin", self.github_branch
            ], cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Repository updated successfully")
                return True
            else:
                logger.warning(f"Failed to update repository: {result.stderr}")
                return True  # Continue even if pull fails
                
        except Exception as e:
            logger.error(f"Error updating repository: {str(e)}")
            return True  # Continue even if update fails
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a file from the repository"""
        try:
            full_path = os.path.join(self.repo_path, file_path)
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning(f"File not found: {file_path}")
                return None
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return None
    
    def write_file_content(self, file_path: str, content: str) -> bool:
        """Write content to a file in the repository"""
        try:
            full_path = os.path.join(self.repo_path, file_path)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Successfully wrote content to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {str(e)}")
            return False
    
    def list_files(self, extension_filter: Optional[str] = None) -> list:
        """List all files in the repository"""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.repo_path):
                # Skip .git directory
                if '.git' in dirs:
                    dirs.remove('.git')
                
                for filename in filenames:
                    if extension_filter and not filename.endswith(extension_filter):
                        continue
                    
                    rel_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                    files.append(rel_path.replace('\\', '/'))
            
            return files
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return []
    
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in the repository"""
        full_path = os.path.join(self.repo_path, file_path)
        return os.path.exists(full_path)

# Global instance
repo_manager = RepositoryManager()
