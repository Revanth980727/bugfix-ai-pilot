
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service-test")

# Add the current directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_github_service():
    """Test the GitHub service functionality"""
    from github_service.github_service import GitHubService
    
    # Initialize service
    service = GitHubService()
    
    # Test creating a branch
    ticket_id = "TEST-123"
    branch_name = service.create_fix_branch(ticket_id)
    if not branch_name:
        logger.error("Failed to create branch")
        return
    
    # Test committing changes
    test_changes = [
        {
            "filename": "test.md",
            "content": f"# Test File\n\nCreated by GitHub service test at {datetime.now()}"
        }
    ]
    
    commit_success = service.commit_bug_fix(
        branch_name,
        test_changes,
        ticket_id,
        "Test commit for automated testing"
    )
    
    if not commit_success:
        logger.error("Failed to commit changes")
        return
    
    # Test creating PR
    pr_url = service.create_fix_pr(
        branch_name,
        ticket_id,
        "Test bug fix",
        "This is a test PR created by the GitHub service test script"
    )
    
    if not pr_url:
        logger.error("Failed to create PR")
        return
    
    logger.info("All GitHub service tests passed successfully!")
    logger.info(f"Created PR: {pr_url}")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run tests
    test_github_service()
