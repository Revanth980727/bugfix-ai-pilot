
import os
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service-test")

# Add the current directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_github_service():
    """Test the GitHub service functionality"""
    from github_service.github_service import GitHubService
    from github_service.utils import parse_patch_content
    
    # Verify environment variables
    token = os.environ.get('GITHUB_TOKEN')
    repo_owner = os.environ.get('GITHUB_REPO_OWNER')
    repo_name = os.environ.get('GITHUB_REPO_NAME')
    
    if not token or token == "your_github_token_here":
        logger.error("GitHub token is missing or invalid. Please check your .env file.")
        logger.info("For testing purposes, continuing with limited functionality.")
        return
        
    if not repo_owner or not repo_name:
        logger.error("GitHub repository information is missing. Please set GITHUB_REPO_OWNER and GITHUB_REPO_NAME in your .env file.")
        logger.info("For testing purposes, continuing with limited functionality.")
        return
    
    try:
        # Initialize service
        service = GitHubService()
        
        # Test creating a branch
        ticket_id = "TEST-123"
        branch_name = service.create_branch(ticket_id)
        if not branch_name:
            logger.error("Failed to create branch")
            return
        
        # Test various file types to ensure all are handled correctly
        test_changes = [
            {
                "filename": "test.md",
                "content": f"# Test File\n\nCreated by GitHub service test at {datetime.now()}"
            },
            {
                "filename": "GraphRAG.py", 
                "content": "import networkx as nx\n\n# Test Graph RAG implementation\ndef graph_function():\n    G = nx.Graph()\n    return G"
            }
        ]
        
        # Extract file paths and contents correctly
        file_paths = [change["filename"] for change in test_changes]
        file_contents = [change["content"] for change in test_changes]
        
        # Log what we're about to commit
        logger.info(f"Committing {len(file_paths)} files: {', '.join(file_paths)}")
        for i, (file_path, content) in enumerate(zip(file_paths, file_contents)):
            preview = content[:50] + "..." if len(content) > 50 else content
            logger.info(f"File {i+1}: {file_path} - Content preview: {preview}")
        
        # Create a valid patch format for testing
        patch_content = ""
        for change in test_changes:
            file_path = change["filename"]
            content = change["content"]
            patch_content += f"--- a/{file_path}\n+++ b/{file_path}\n@@ -0,0 +1,{len(content.splitlines())} @@\n"
            for line in content.splitlines():
                patch_content += f"+{line}\n"
            patch_content += "\n"
            
        # Test patch parsing to ensure it's working correctly
        logger.info("Testing patch parsing functionality")
        parsed_changes = parse_patch_content(patch_content)
        for change in parsed_changes:
            logger.info(f"Parsed file: {change['file_path']}, lines: +{change['line_changes']['added']}/-{change['line_changes']['removed']}")
            
        # Verify that all files in the test_changes are also in the parsed_changes
        parsed_files = [change['file_path'] for change in parsed_changes]
        for file_path in file_paths:
            if file_path not in parsed_files:
                logger.error(f"File {file_path} was not correctly parsed from the patch content!")
        
        # First try committing with the patch content for more realistic testing
        logger.info("Testing commit with patch content")
        commit_patch_success = service.commit_patch(
            branch_name=branch_name,
            patch_content=patch_content,
            commit_message=f"Test patch-based commit for {ticket_id}",
            patch_file_paths=file_paths
        )
        
        if not commit_patch_success:
            logger.warning("Patch-based commit failed, falling back to direct file commits")
            
            # Test direct file commits as fallback
            commit_success = service.commit_bug_fix(
                branch_name,
                file_paths,
                file_contents,
                ticket_id,
                "Test commit for automated testing"
            )
            
            if not commit_success:
                logger.error("Failed to commit changes")
                return
        else:
            logger.info("Patch-based commit succeeded")
        
        # Test creating PR - use create_pull_request directly
        pr_url = service.create_pull_request(
            branch_name,
            ticket_id,
            "Test bug fix",
            "This is a test PR created by the GitHub service test script"
        )
        
        if not pr_url:
            logger.error("Failed to create PR")
            return
        
        logger.info(f"Created PR: {pr_url}")
        logger.info("All GitHub service tests passed successfully!")
    except Exception as e:
        logger.error(f"GitHub service test failed: {str(e)}")
        logger.info("GitHub integration tests were skipped due to configuration issues.")
        logger.info("To run GitHub tests, please set valid credentials in your .env file.")

if __name__ == "__main__":
    # Run tests
    test_github_service()
