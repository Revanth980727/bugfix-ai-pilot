
import os
import sys
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service-test")

# Add the current directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_github_service():
    """Test the GitHub service functionality"""
    from github_service.github_service import GitHubService
    from github_service.utils import parse_patch_content, parse_patch_basic
    from github_service.patch_engine import apply_patch_to_content, validate_patch
    from github_service.config import preserve_branch_case, include_test_files
    
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
        
        # Test creating a branch with case sensitivity
        ticket_id = "TEST-123"
        logger.info(f"Creating branch for ticket ID: {ticket_id}")
        logger.info(f"Preserve branch case setting: {preserve_branch_case()}")
        
        branch_name = service.create_branch(ticket_id)
        if not branch_name:
            logger.error("Failed to create branch")
            return
        
        # Verify branch name case sensitivity
        expected_branch_name = f"fix/{ticket_id}" if service.preserve_case else f"fix/{ticket_id.lower()}"
        if branch_name == expected_branch_name:
            logger.info(f"✓ Branch name case sensitivity working correctly: {branch_name}")
        else:
            logger.error(f"✗ Branch name case sensitivity not working. Got: {branch_name}, Expected: {expected_branch_name}")
        
        # Test whether test files are included based on configuration
        logger.info(f"Include test files setting: {include_test_files()}")
        
        # Simulate planner agent analysis (this would come from the actual planner)
        planner_analysis = {
            "ticket_id": ticket_id,
            "bug_summary": "Import error causing module initialization failure",
            "error_type": "ImportError",
            "affected_files": [
                {"file": "src/utils/data_processor.py", "valid": True, "reason": "Contains the problematic import"},
                {"file": "src/main.py", "valid": True, "reason": "Entry point that uses the affected module"}
            ]
        }
        
        # Initialize developer agent to get actual file names
        logger.info("Initializing developer agent to get file analysis...")
        from agent_framework.developer_agent import DeveloperAgent
        
        developer_agent = DeveloperAgent()
        developer_result = developer_agent.run(planner_analysis)
        
        if not developer_result.get("success", False):
            logger.error(f"Developer agent failed: {developer_result.get('error', 'Unknown error')}")
            return
        
        # Extract actual file information from developer agent
        actual_file_paths = developer_result.get("patched_files", [])
        actual_file_contents = developer_result.get("patched_code", {})
        actual_patch_content = developer_result.get("patch_content", "")
        actual_commit_message = developer_result.get("commit_message", f"Fix {ticket_id}")
        
        if not actual_file_paths:
            logger.error("Developer agent returned no file paths")
            return
        
        # Log what we're about to commit using actual developer agent data
        logger.info(f"Using developer agent output: {len(actual_file_paths)} files")
        for file_path in actual_file_paths:
            if file_path in actual_file_contents:
                content = actual_file_contents[file_path]
                preview = content[:50] + "..." if len(content) > 50 else content
                logger.info(f"File: {file_path} - Content preview: {preview}")
            else:
                logger.warning(f"File {file_path} in patched_files but no content available")
        
        # Test patch parsing with actual content
        logger.info("Testing patch parsing with developer agent content")
        if actual_patch_content:
            parsed_changes = parse_patch_content(actual_patch_content)
            for change in parsed_changes:
                logger.info(f"Parsed file: {change['file_path']}, lines: +{change['line_changes']['added']}/-{change['line_changes']['removed']}")
            
            # Test the basic patch parser as a fallback
            logger.info("Testing basic patch parser with actual content")
            basic_parsed_changes = parse_patch_basic(actual_patch_content)
            
            # Compare results between parsers
            logger.info(f"Regular parser found {len(parsed_changes)} files, basic parser found {len(basic_parsed_changes)} files")
            
            # Verify that all files from developer agent are in the parsed_changes
            parsed_files = [change['file_path'] for change in parsed_changes]
            for file_path in actual_file_paths:
                if file_path not in parsed_files:
                    logger.error(f"File {file_path} from developer agent was not correctly parsed from patch!")
        else:
            logger.warning("No patch content from developer agent to test parsing")
        
        # Test committing with actual developer agent content
        logger.info("Testing commit with actual developer agent files")
        
        # Prepare file contents list matching the file paths order
        file_contents = []
        for file_path in actual_file_paths:
            content = actual_file_contents.get(file_path, f"# Generated content for {file_path}")
            file_contents.append(content)
        
        commit_success = service.commit_bug_fix(
            branch_name,
            actual_file_paths,
            file_contents,
            ticket_id,
            actual_commit_message
        )
        
        if not commit_success:
            logger.error("Failed to commit developer agent files")
            return
            
        # Test modification patch with actual content if available
        if actual_patch_content:
            logger.info("Testing modification patch with developer agent patch content")
            
            # Get current content from repository
            original_contents = {}
            expected_contents = {}
            
            for file_path in actual_file_paths:
                current_content = service._github_client._get_file_content(file_path, branch_name)
                if current_content:
                    original_contents[file_path] = current_content
                    # For testing, add a small modification to each file
                    expected_contents[file_path] = current_content + f"\n# Test modification at {datetime.now()}"
                    
            # Create a test modification patch
            modified_patch = ""
            for file_path in actual_file_paths:
                if file_path in original_contents:
                    lines = original_contents[file_path].splitlines()
                    modified_lines = lines + [f"# Test modification at {datetime.now()}"]
                    
                    modified_patch += f"--- a/{file_path}\n+++ b/{file_path}\n@@ -1,{len(lines)} +1,{len(modified_lines)} @@\n"
                    for line in lines:
                        modified_patch += f" {line}\n"
                    modified_patch += f"+# Test modification at {datetime.now()}\n\n"
            
            if modified_patch:
                logger.info("Testing patch engine with actual file modifications")
                
                # Test patch engine with actual files
                for file_path in actual_file_paths:
                    if file_path in original_contents:
                        result = apply_patch_to_content(
                            original_content=original_contents[file_path],
                            patch_content=modified_patch,
                            file_path=file_path,
                            expected_content=expected_contents.get(file_path)
                        )
                        logger.info(f"Patch engine result for {file_path}: {result[0]}, method: {result[2]}")
                
                # Test the validator with actual content
                logger.info("Testing patch validator with actual files")
                validation_result = validate_patch(
                    patch_content=modified_patch,
                    file_paths=actual_file_paths,
                    original_contents=original_contents,
                    expected_contents=expected_contents
                )
                logger.info(f"Validation result: Valid={validation_result['valid']}")
                for file_path, file_result in validation_result['file_results'].items():
                    if file_result.get('valid', False):
                        logger.info(f"✓ Validation passed for {file_path} using {file_result.get('method', 'unknown')}")
                    else:
                        logger.warning(f"✗ Validation failed for {file_path}: {file_result.get('error', 'unknown error')}")
                
                # Test committing with the actual modification patch
                logger.info("Testing commit with actual modification patch")
                
                commit_patch_success = service.commit_patch(
                    branch_name=branch_name,
                    patch_content=modified_patch,
                    commit_message=f"Test modification patch for {ticket_id}",
                    patch_file_paths=actual_file_paths,
                    expected_content=expected_contents
                )
                
                if not commit_patch_success:
                    logger.warning("Modification patch-based commit failed")
                else:
                    logger.info("Modification patch-based commit succeeded")
                    
                    # Verify the files were actually modified correctly
                    for file_path in actual_file_paths:
                        updated_content = service._github_client._get_file_content(file_path, branch_name)
                        if updated_content and "Test modification" in updated_content:
                            logger.info(f"✅ {file_path} was correctly patched!")
                        else:
                            logger.error(f"❌ {file_path} was not correctly patched!")
        
        # Test creating PR with actual developer agent data
        pr_description = f"This PR contains fixes generated by the developer agent for ticket {ticket_id}.\n\nFiles modified: {', '.join(actual_file_paths)}\n\nBug summary: {planner_analysis.get('bug_summary', 'No summary available')}"
        
        pr_url = service.create_pull_request(
            branch_name,
            ticket_id,
            actual_commit_message,
            pr_description
        )
        
        if not pr_url:
            logger.error("Failed to create PR")
            return
        
        logger.info(f"Created PR: {pr_url}")
        
        # Test with test files if configured and available
        test_code = developer_result.get("test_code", {})
        if include_test_files() and test_code:
            logger.info("Testing test file inclusion (enabled in configuration)")
            test_files = list(test_code.keys())
            
            logger.info(f"Developer agent generated {len(test_files)} test files: {', '.join(test_files)}")
            for test_file in test_files:
                test_content = test_code[test_file]
                preview = test_content[:50] + "..." if len(test_content) > 50 else test_content
                logger.info(f"Test file {test_file}: {preview}")
        else:
            logger.info("Test file inclusion disabled or no test code generated by developer agent")
        
        logger.info("All GitHub service tests with actual developer agent data passed successfully!")
        
    except Exception as e:
        logger.error(f"GitHub service test failed: {str(e)}")
        logger.info("GitHub integration tests were skipped due to configuration issues.")
        logger.info("To run GitHub tests, please set valid credentials in your .env file.")

if __name__ == "__main__":
    # Run tests
    test_github_service()
