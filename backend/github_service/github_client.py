
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
        self.token = GITHUB_TOKEN
        self.pr_mapping = {}  # Store ticket ID to PR number mappings
        
        # Verify token is valid
        try:
            if not GITHUB_TOKEN or GITHUB_TOKEN == "your_github_token_here":
                logger.error("Invalid GitHub token. Please set a valid GITHUB_TOKEN in .env")
                raise ValueError("Invalid GitHub token. Please set a valid GITHUB_TOKEN in .env")
                
            if not GITHUB_REPO_OWNER or not GITHUB_REPO_NAME:
                logger.error("GitHub repository owner or name not specified")
                raise ValueError("GitHub repository owner or name not specified")
            
            # Test authentication
            self.client.get_user().login
            
            # Get repository reference
            self.repo = self.client.get_repo(f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
            logger.info(f"Successfully connected to GitHub repository: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
            
        except GithubException as e:
            if e.status == 401:
                logger.error("GitHub authentication failed: Bad credentials. Check your GITHUB_TOKEN.")
                self.repo = None
            elif e.status == 404:
                logger.error(f"Repository {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME} not found. Check your repository settings.")
                self.repo = None
            else:
                logger.error(f"GitHub API error: {str(e)}")
                self.repo = None
            raise
    
    def get_file_content(self, file_path: str, branch: str = None) -> str:
        """Get the content of a file from the repository"""
        try:
            if not self.repo:
                logger.error("Repository connection not established")
                return ""
                
            # If branch is not specified, use the default branch
            if not branch:
                branch = self.repo.default_branch
                
            # Get the file content
            file_content = self.repo.get_contents(file_path, ref=branch)
            
            # If file_content is a list, it means it's a directory
            if isinstance(file_content, list):
                logger.error(f"{file_path} is a directory, not a file")
                return ""
                
            # Decode content if it's a file
            return file_content.decoded_content.decode('utf-8')
            
        except GithubException as e:
            logger.error(f"Failed to get file content for {file_path}: {str(e)}")
            return ""
    
    def create_branch(self, branch_name: str, base_branch: str = None) -> Optional[str]:
        """Create a new branch from the specified base branch."""
        try:
            if not self.repo:
                logger.error("Repository connection not established")
                return None
                
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
            if not self.repo:
                logger.error("Repository connection not established")
                return False
                
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
    
    def check_for_existing_pr(self, head_branch: str, base_branch: str = None) -> Optional[Dict[str, Any]]:
        """
        Check if a PR already exists for the specified branches
        
        Args:
            head_branch: Source branch
            base_branch: Target branch
            
        Returns:
            Dict with PR details or None if no PR exists
        """
        try:
            if not self.repo:
                logger.error("Repository connection not established")
                return None
                
            if not base_branch:
                base_branch = self.repo.default_branch
                
            # Look for open PRs with matching head and base branches
            existing_prs = self.repo.get_pulls(
                state='open',
                head=f"{GITHUB_REPO_OWNER}:{head_branch}",
                base=base_branch
            )
            
            # Return the first matching PR if any
            for pr in existing_prs:
                logger.info(f"Found existing PR #{pr.number}: {pr.html_url}")
                
                # Extract the ticket ID from branch name if it follows fix/TICKET-ID pattern
                ticket_match = re.search(r'fix/([A-Z]+-\d+)', head_branch)
                if ticket_match:
                    ticket_id = ticket_match.group(1)
                    self.pr_mapping[ticket_id] = pr.number
                    logger.info(f"Mapped ticket {ticket_id} to PR #{pr.number}")
                
                return {
                    'number': pr.number,
                    'url': pr.html_url,
                    'title': pr.title,
                    'body': pr.body
                }
                
            return None
            
        except GithubException as e:
            logger.error(f"Error checking for existing PRs: {str(e)}")
            return None
    
    def create_pull_request(self, title: str, body: str,
                          head_branch: str, base_branch: str = None) -> Optional[Dict[str, Any]]:
        """Create a pull request from the specified branch."""
        try:
            if not self.repo:
                logger.error("Repository connection not established")
                return None
                
            if not base_branch:
                base_branch = self.repo.default_branch
            
            # Check for existing PR first
            existing_pr = self.check_for_existing_pr(head_branch, base_branch)
            if existing_pr:
                logger.info(f"Using existing PR: {existing_pr['url']}")
                return existing_pr
            
            # Create new PR if none exists
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            
            # Extract the ticket ID from branch name if it follows fix/TICKET-ID pattern
            ticket_match = re.search(r'fix/([A-Z]+-\d+)', head_branch)
            if ticket_match:
                ticket_id = ticket_match.group(1)
                self.pr_mapping[ticket_id] = pr.number
                logger.info(f"Mapped ticket {ticket_id} to PR #{pr.number}")
            
            logger.info(f"Created new pull request: {pr.html_url}")
            return {
                'number': pr.number,
                'url': pr.html_url,
                'title': pr.title,
                'body': pr.body
            }
            
        except GithubException as e:
            if e.status == 422:
                # This often means a PR already exists but wasn't found by check_for_existing_pr
                # Try to find it again with a broader search
                logger.warning(f"PR creation failed with 422 status, may already exist. Attempting broader search.")
                try:
                    # Look for any open PRs from this head branch
                    for pr in self.repo.get_pulls(state='open'):
                        if pr.head.ref == head_branch:
                            
                            # Extract the ticket ID from branch name
                            ticket_match = re.search(r'fix/([A-Z]+-\d+)', head_branch)
                            if ticket_match:
                                ticket_id = ticket_match.group(1)
                                self.pr_mapping[ticket_id] = pr.number
                                logger.info(f"Mapped ticket {ticket_id} to PR #{pr.number}")
                                
                            logger.info(f"Found existing PR after error: {pr.html_url}")
                            return {
                                'number': pr.number,
                                'url': pr.html_url,
                                'title': pr.title,
                                'body': pr.body
                            }
                except Exception as search_error:
                    logger.error(f"Error in broader PR search: {str(search_error)}")
                    
            logger.error(f"Failed to create pull request: {str(e)}")
            return None

    def extract_pr_number(self, pr_identifier: str) -> Optional[int]:
        """
        Extract a numeric PR number from various formats
        
        Args:
            pr_identifier: PR identifier (number, URL, or other string)
            
        Returns:
            int: PR number if found, None otherwise
        """
        try:
            # If it's a numeric string, convert directly
            if isinstance(pr_identifier, str) and pr_identifier.isdigit():
                return int(pr_identifier)
                
            # If it's a JIRA ticket ID that we have mapped to a PR
            if isinstance(pr_identifier, str) and pr_identifier in self.pr_mapping:
                logger.info(f"Using mapped PR #{self.pr_mapping[pr_identifier]} for ticket {pr_identifier}")
                return self.pr_mapping[pr_identifier]
            
            # Try to extract PR number from a URL
            if isinstance(pr_identifier, str) and '/' in pr_identifier:
                # For URL format: https://github.com/owner/repo/pull/123
                parts = pr_identifier.split('/')
                for i, part in enumerate(parts):
                    if part == "pull" and i+1 < len(parts) and parts[i+1].isdigit():
                        return int(parts[i+1])
            
            # For GitHub's short URL format: owner/repo#123
            if isinstance(pr_identifier, str) and '#' in pr_identifier:
                parts = pr_identifier.split('#')
                if len(parts) > 1 and parts[1].isdigit():
                    return int(parts[1])
            
            # If it's already a numeric type
            if isinstance(pr_identifier, int):
                return pr_identifier
                
            # Don't extract numbers from JIRA ticket IDs
            if isinstance(pr_identifier, str) and re.match(r'^[A-Z]+-\d+$', pr_identifier):
                logger.info(f"Not extracting numbers from JIRA ticket ID: {pr_identifier}")
                
                # Instead, try to find a PR for this ticket
                try:
                    # Look for PRs with this ticket ID in title or branch name
                    for pr in self.repo.get_pulls(state='open'):
                        if pr_identifier in pr.title or f"fix/{pr_identifier}" == pr.head.ref:
                            self.pr_mapping[pr_identifier] = pr.number
                            logger.info(f"Found PR #{pr.number} for ticket {pr_identifier}")
                            return pr.number
                except Exception as e:
                    logger.error(f"Error searching for PR by ticket ID: {str(e)}")
                
                return None
                
            logger.warning(f"Could not extract PR number from: {pr_identifier}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting PR number: {str(e)}")
            return None

    def add_pr_comment(self, pr_identifier: Any, comment: str) -> bool:
        """
        Add a comment to a pull request, handling various PR identifier formats
        
        Args:
            pr_identifier: The PR identifier (number, URL, or other string)
            comment: The comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.repo:
                logger.error("Repository connection not established")
                return False
                
            # Extract PR number from the identifier
            pr_number = self.extract_pr_number(pr_identifier)
            if pr_number is None:
                logger.error(f"Could not extract PR number from: {pr_identifier}")
                return False
                
            logger.info(f"Adding comment to PR #{pr_number}")
            
            # Get PR and add comment
            try:
                pr = self.repo.get_pull(pr_number)
                pr.create_issue_comment(comment)
                
                logger.info(f"Successfully added comment to PR #{pr_number}")
                return True
                
            except GithubException as pr_error:
                if pr_error.status == 404:
                    logger.error(f"PR #{pr_number} not found or cannot be accessed: {str(pr_error)}")
                    return False
                else:
                    logger.error(f"GitHub error adding comment to PR: {str(pr_error)}")
                    return False
                
        except Exception as e:
            logger.error(f"Unexpected error adding comment to PR: {str(e)}")
            return False
