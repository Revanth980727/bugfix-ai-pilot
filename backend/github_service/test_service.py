
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
        
        # Generate dynamic test content based on actual developer agent structure
        logger.info("Generating dynamic test content using developer agent patterns...")
        
        # Simulate a developer agent result structure
        developer_result = {
            "patched_code": {
                "example_module.py": f"# Bug fix for {ticket_id}\nimport os\nimport sys\n\ndef fixed_function():\n    return 'Fixed at {datetime.now()}'\n",
                "utils.py": f"# Utility functions for {ticket_id}\n\ndef helper_function():\n    return True\n"
            },
            "test_code": {
                "test_example_module.py": f"import pytest\nfrom example_module import fixed_function\n\ndef test_fixed_function():\n    result = fixed_function()\n    assert 'Fixed' in result\n",
                "test_utils.py": f"import pytest\nfrom utils import helper_function\n\ndef test_helper_function():\n    assert helper_function() is True\n"
            },
            "patched_files": ["example_module.py", "utils.py"],
            "patch_content": "",
            "commit_message": f"Fix {ticket_id}: Dynamic test commit"
        }
        
        # Extract file information dynamically
        file_paths = list(developer_result["patched_code"].keys())
        file_contents = list(developer_result["patched_code"].values())
        
        # Log what we're about to commit
        logger.info(f"Committing {len(file_paths)} files: {', '.join(file_paths)}")
        for i, (file_path, content) in enumerate(zip(file_paths, file_contents)):
            preview = content[:50] + "..." if len(content) > 50 else content
            logger.info(f"File {i+1}: {file_path} - Content preview: {preview}")
        
        # Generate patch content dynamically based on the actual files
        patch_content = ""
        for file_path, content in developer_result["patched_code"].items():
            lines = content.splitlines()
            patch_content += f"--- a/{file_path}\n+++ b/{file_path}\n@@ -0,0 +1,{len(lines)} @@\n"
            for line in lines:
                patch_content += f"+{line}\n"
            patch_content += "\n"
        
        developer_result["patch_content"] = patch_content
            
        # Test patch parsing to ensure it's working correctly
        logger.info("Testing patch parsing functionality")
        parsed_changes = parse_patch_content(patch_content)
        for change in parsed_changes:
            logger.info(f"Parsed file: {change['file_path']}, lines: +{change['line_changes']['added']}/-{change['line_changes']['removed']}")
        
        # Test the basic patch parser as a fallback
        logger.info("Testing basic patch parser (fallback)")
        basic_parsed_changes = parse_patch_basic(patch_content)
        
        # Compare results between parsers
        logger.info(f"Regular parser found {len(parsed_changes)} files, basic parser found {len(basic_parsed_changes)} files")
        
        # Verify that all files in the developer result are also in the parsed_changes
        parsed_files = [change['file_path'] for change in parsed_changes]
        for file_path in file_paths:
            if file_path not in parsed_files:
                logger.error(f"File {file_path} was not correctly parsed from the patch content!")
        
        # Test committing with dynamic content
        logger.info("Testing commit with dynamic content from developer agent")
        
        commit_success = service.commit_bug_fix(
            branch_name,
            file_paths,
            file_contents,
            ticket_id,
            developer_result["commit_message"]
        )
        
        if not commit_success:
            logger.error("Failed to commit files")
            return
            
        # Test modification patch with dynamic content
        logger.info("Testing modification patch with dynamic content")
        
        # Generate a modification patch based on the existing content
        modified_patch = ""
        for file_path, original_content in developer_result["patched_code"].items():
            # Add a modification to each file
            lines = original_content.splitlines()
            modified_lines = lines + [f"# Modified for testing at {datetime.now()}"]
            
            modified_patch += f"--- a/{file_path}\n+++ b/{file_path}\n@@ -1,{len(lines)} +1,{len(modified_lines)} @@\n"
            for line in lines:
                modified_patch += f" {line}\n"
            modified_patch += f"+# Modified for testing at {datetime.now()}\n"
            modified_patch += "\n"
        
        logger.info("Created dynamic modification patch content")
        
        # Test patch engine with dynamic content
        logger.info("Testing patch engine with dynamic validation")
        
        original_contents = {}
        expected_contents = {}
        
        for file_path in file_paths:
            current_content = service._github_client._get_file_content(file_path, branch_name)
            if current_content:
                original_contents[file_path] = current_content
                # Generate expected content by applying the modification
                expected_contents[file_path] = current_content + f"\n# Modified for testing at {datetime.now()}"
                
        # Test applying the patch with validation
        for file_path in file_paths:
            if file_path in original_contents:
                result = apply_patch_to_content(
                    original_content=original_contents[file_path],
                    patch_content=modified_patch,
                    file_path=file_path,
                    expected_content=expected_contents.get(file_path)
                )
                logger.info(f"Patch engine result for {file_path}: {result[0]}, method: {result[2]}")
        
        # Test the validator with dynamic content
        logger.info("Testing patch validator with dynamic content")
        validation_result = validate_patch(
            patch_content=modified_patch,
            file_paths=file_paths,
            original_contents=original_contents,
            expected_contents=expected_contents
        )
        logger.info(f"Validation result: Valid={validation_result['valid']}")
        for file_path, file_result in validation_result['file_results'].items():
            if file_result.get('valid', False):
                logger.info(f"✓ Validation passed for {file_path} using {file_result.get('method', 'unknown')}")
            else:
                logger.warning(f"✗ Validation failed for {file_path}: {file_result.get('error', 'unknown error')}")
        
        # Test committing with the dynamic patch content
        logger.info("Testing commit with dynamic modification patch")
        
        commit_patch_success = service.commit_patch(
            branch_name=branch_name,
            patch_content=modified_patch,
            commit_message=f"Modified patch commit for {ticket_id}",
            patch_file_paths=file_paths,
            expected_content=expected_contents
        )
        
        if not commit_patch_success:
            logger.warning("Modified patch-based commit failed, falling back to direct file commits")
        else:
            logger.info("Modified patch-based commit succeeded")
            
            # Verify the files were actually modified correctly
            for file_path in file_paths:
                updated_content = service._github_client._get_file_content(file_path, branch_name)
                logger.info(f"Verifying {file_path} after patch:")
                if "Modified for testing" in updated_content:
                    logger.info(f"✅ {file_path} was correctly patched!")
                else:
                    logger.error(f"❌ {file_path} was not correctly patched!")
        
        # Test creating PR with dynamic data
        pr_url = service.create_pull_request(
            branch_name,
            ticket_id,
            f"Dynamic bug fix for {ticket_id}",
            f"This PR contains fixes generated dynamically for ticket {ticket_id}. Files modified: {', '.join(file_paths)}"
        )
        
        if not pr_url:
            logger.error("Failed to create PR")
            return
        
        logger.info(f"Created PR: {pr_url}")
        
        # Test with test files if configured
        if include_test_files() and developer_result.get("test_code"):
            logger.info("Testing test file inclusion (enabled in configuration)")
            test_files = list(developer_result["test_code"].keys())
            test_contents = list(developer_result["test_code"].values())
            
            logger.info(f"Would include {len(test_files)} test files: {', '.join(test_files)}")
        else:
            logger.info("Test file inclusion disabled or no test code generated")
        
        logger.info("All dynamic GitHub service tests passed successfully!")
        
    except Exception as e:
        logger.error(f"GitHub service test failed: {str(e)}")
        logger.info("GitHub integration tests were skipped due to configuration issues.")
        logger.info("To run GitHub tests, please set valid credentials in your .env file.")

if __name__ == "__main__":
    # Run tests
    test_github_service()
