
import logging
from typing import Dict, Any, Optional, List
from github import Github, GithubException
from .config import GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-client")

class GitHubClient:
    def __init__(self):
        self.client = Github(GITHUB_TOKEN)
        self.repo = self.client.get_repo(f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
    
    def create_branch(self, branch_name: str, base_branch: str = None) -> Optional[str]:
        """Create a new branch from the specified base branch."""
        try:
            # Get the base branch
            if not base_branch:
                base_branch = self.repo.default_branch
            
            base_ref = self.repo.get_branch(base_branch)
            
            # Check if branch exists
            try:
                self.repo.get_branch(branch_name)
                logger.info(f"Branch {branch_name} already exists")
                return branch_name
            except GithubException:
                # Create the branch
                self.repo.create_git_ref(f"refs/heads/{branch_name}", base_ref.commit.sha)
                logger.info(f"Created branch {branch_name} from {base_branch}")
                return branch_name
                
        except GithubException as e:
            logger.error(f"Failed to create branch: {str(e)}")
            return None
    
    def commit_changes(self, branch_name: str, file_changes: List[Dict[str, Any]], 
                      commit_message: str) -> bool:
        """Commit multiple file changes to a branch."""
        try:
            # Get the latest commit on the branch
            ref = self.repo.get_git_ref(f"heads/{branch_name}")
            latest_commit = self.repo.get_git_commit(ref.object.sha)
            base_tree = latest_commit.tree
            
            # Create tree elements for the changes
            tree_elements = []
            for change in file_changes:
                blob = self.repo.create_git_blob(change['content'], 'utf-8')
                element = {
                    'path': change['filename'],
                    'mode': '100644',
                    'type': 'blob',
                    'sha': blob.sha
                }
                tree_elements.append(element)
            
            # Create a new tree with the changes
            new_tree = self.repo.create_git_tree(tree_elements, base_tree)
            
            # Create the commit
            new_commit = self.repo.create_git_commit(
                message=commit_message,
                tree=new_tree,
                parents=[latest_commit]
            )
            
            # Update the reference
            ref.edit(new_commit.sha)
            logger.info(f"Committed {len(tree_elements)} files to {branch_name}")
            return True
            
        except GithubException as e:
            logger.error(f"Failed to commit changes: {str(e)}")
            return False
    
    def create_pull_request(self, branch_name: str, title: str, body: str,
                          base_branch: str = None) -> Optional[str]:
        """Create a pull request from the specified branch."""
        try:
            if not base_branch:
                base_branch = self.repo.default_branch
            
            # Check for existing PR
            existing_prs = self.repo.get_pulls(
                state='open',
                head=f"{GITHUB_REPO_OWNER}:{branch_name}",
                base=base_branch
            )
            
            for pr in existing_prs:
                logger.info(f"Pull request already exists: {pr.html_url}")
                return pr.html_url
            
            # Create new PR
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch
            )
            
            logger.info(f"Created pull request: {pr.html_url}")
            return pr.html_url
            
        except GithubException as e:
            logger.error(f"Failed to create pull request: {str(e)}")
            return None
