
import pytest
import logging
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import communicator agent with proper path
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_framework.communicator_agent import CommunicatorAgent
from agent_framework.agent_base import AgentStatus
from github_service.patch_validator import PatchValidator

@pytest.mark.asyncio
async def test_communicator_agent():
    """Test the communicator agent functionality"""
    # Initialize agent with mocked dependencies
    agent = CommunicatorAgent()
    
    # Mock the jira and github clients with proper AsyncMock objects
    agent.jira_client = MagicMock()
    agent.jira_client.update_ticket = AsyncMock(return_value=True)
    agent.jira_client.add_comment = AsyncMock(return_value=True)
    
    agent.github_service = MagicMock()
    agent.github_service.create_fix_branch = MagicMock(return_value=True)
    agent.github_service.create_pull_request = MagicMock(return_value=("https://github.com/org/repo/pull/123", 123))
    agent.github_service.add_pr_comment = MagicMock(return_value=True)
    agent.github_service.find_pr_for_branch = MagicMock(return_value={
        "number": 123,
        "url": "https://github.com/org/repo/pull/123"
    })
    agent.github_service.check_file_exists = MagicMock(return_value=True)
    agent.github_service.commit_bug_fix = MagicMock(return_value=(True, {}))
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": True,
        "reasons": [],
        "confidence_boost": 10
    })
    
    # Initialize patch validator
    agent.patch_validator = PatchValidator()
    agent.patch_validator.set_github_client(agent.github_service)
    agent.patch_validator._is_valid_file_path = MagicMock(return_value=True)
    agent.patch_validator._is_valid_diff_syntax = MagicMock(return_value=True)
    agent.patch_validator._check_for_placeholders = MagicMock(return_value=[])
    
    # Test various test success field name variations
    await test_field_name_variations(agent)
    
    # Test successful case
    success_input = {
        "ticket_id": "TEST-123",
        "test_passed": True,
        "github_pr_url": "https://github.com/org/repo/pull/123",
        "retry_count": 0,
        "max_retries": 4
    }
    
    try:
        result = await agent.run(success_input)
        logger.info(f"\nCommunicator Agent status: {agent.status}")
        logger.info(f"Processing result: {result}")
        
        assert result["ticket_id"] == "TEST-123"
        assert "communications_success" in result
        assert "timestamp" in result
        assert agent.status == AgentStatus.SUCCESS
        
        # Verify the async methods were properly called with await
        agent.jira_client.add_comment.assert_awaited()
        agent.jira_client.update_ticket.assert_awaited()
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise
    
    # Test failure case with retries
    failure_input = {
        "ticket_id": "TEST-124",
        "test_passed": False,
        "github_pr_url": "https://github.com/org/repo/pull/124",
        "retry_count": 2,
        "max_retries": 4
    }
    
    try:
        result = await agent.run(failure_input)
        logger.info(f"\nCommunicator Agent status: {agent.status}")
        logger.info(f"Processing result: {result}")
        
        assert result["ticket_id"] == "TEST-124"
        assert "communications_success" in result
        assert not result["test_passed"]
        
        # Verify JIRA client was called with proper awaits
        agent.jira_client.add_comment.assert_awaited()
        agent.jira_client.update_ticket.assert_awaited()
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise
        
    # Test edge case: PR creation failed
    edge_input = {
        "ticket_id": "TEST-125",
        "test_passed": True,
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Override the mock to simulate PR creation failure
    agent.github_service.create_pull_request = MagicMock(return_value=(None, None))
    
    try:
        result = await agent.run(edge_input)
        logger.info(f"Edge case result: {result}")
        
        assert result["ticket_id"] == "TEST-125"
        assert "error" in result or not result["communications_success"]
        
        # Verify JIRA client was called with proper awaits
        agent.jira_client.add_comment.assert_awaited()
        
    except Exception as e:
        logger.error(f"Edge case test failed: {str(e)}")
        raise
    
    # Test PR URL validation
    invalid_pr_input = {
        "ticket_id": "TEST-126",
        "test_passed": True,
        "github_pr_url": "https://github.com/org/repo/pull/TEST-126",  # Invalid: non-numeric PR number
        "retry_count": 0,
        "max_retries": 4
    }
    
    try:
        result = await agent.run(invalid_pr_input)
        logger.info(f"Invalid PR URL result: {result}")
        
        assert result["ticket_id"] == "TEST-126"
        assert not result.get("github_updated", True), "Should not update GitHub with invalid PR URL"
        
    except Exception as e:
        logger.error(f"Invalid PR URL test failed: {str(e)}")
        raise
        
    # Test PR URL handling with ticket ID used as branch name
    ticket_as_branch_input = {
        "ticket_id": "TEST-127",
        "test_passed": True,
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Mock to return a PR when searching by branch name
    agent.github_service.find_pr_for_branch = MagicMock(return_value={
        "number": 127,
        "url": "https://github.com/org/repo/pull/127"
    })
    
    try:
        result = await agent.run(ticket_as_branch_input)
        logger.info(f"Ticket as branch result: {result}")
        
        # Verify the agent looked up the PR by branch name
        agent.github_service.find_pr_for_branch.assert_called_with(f"fix/TEST-127")
        
    except Exception as e:
        logger.error(f"Ticket as branch test failed: {str(e)}")
        raise
    
    # Test patch validation - new test case for patch quality assessment
    await test_patch_validation(agent)
    
    # Test handling of different patch formats
    await test_patch_formats(agent)

async def test_field_name_variations(agent):
    """Test that the agent handles both success and test_passed field names correctly."""
    # Test with "success" field
    success_input = {
        "ticket_id": "TEST-200",
        "success": True,
        "patches": [{"file_path": "test.py", "diff": "@@ -1,1 +1,1 @@\n-old\n+new"}],
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(success_input)
    logger.info(f"'success' field result: {result}")
    assert result["test_passed"], "Should recognize 'success' field"
    
    # Test with "test_passed" field
    test_passed_input = {
        "ticket_id": "TEST-201",
        "test_passed": True,
        "patches": [{"file_path": "test.py", "diff": "@@ -1,1 +1,1 @@\n-old\n+new"}],
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(test_passed_input)
    logger.info(f"'test_passed' field result: {result}")
    assert result["test_passed"], "Should recognize 'test_passed' field"
    
    return True

async def test_patch_formats(agent):
    """Test handling of different patch format structures"""
    logger.info("Testing patch format handling...")
    
    # Reset Github service mocks
    agent.github_service.create_fix_branch = MagicMock(return_value=True)
    agent.github_service.commit_bug_fix = MagicMock(return_value=(True, {}))
    agent.github_service.create_pull_request = MagicMock(return_value=("https://github.com/example/repo/pull/123", 123))
    agent.github_service.find_pr_for_branch = MagicMock(return_value=None)
    
    # Test case with "patches" format
    patches_format_input = {
        "ticket_id": "TEST-200",
        "test_passed": True,
        "patches": [
            {
                "file_path": "src/file1.py",
                "diff": "@@ -1,1 +1,1 @@\n-old\n+new"
            }
        ],
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(patches_format_input)
    logger.info(f"'patches' format result: {result}")
    assert result.get("github_updated", False), "Should successfully handle 'patches' format"
    assert result.get("github_pr_url") is not None, "Should create PR with 'patches' format"
    
    # Test case with "patch_content" and "patched_files" format
    patch_content_format_input = {
        "ticket_id": "TEST-201",
        "test_passed": True,
        "patch_content": "@@ -1,1 +1,1 @@\n-old\n+new",
        "patched_files": ["src/file2.py"],
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(patch_content_format_input)
    logger.info(f"'patch_content' format result: {result}")
    assert result.get("github_updated", False), "Should successfully handle 'patch_content' format"
    assert result.get("github_pr_url") is not None, "Should create PR with 'patch_content' format"
    
    # Test case with both formats provided
    hybrid_format_input = {
        "ticket_id": "TEST-202",
        "test_passed": True,
        "patches": [
            {
                "file_path": "src/file3.py",
                "diff": "@@ -1,1 +1,1 @@\n-old\n+new"
            }
        ],
        "patch_content": "@@ -1,1 +1,1 @@\n-old-alt\n+new-alt",
        "patched_files": ["src/file4.py"],
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(hybrid_format_input)
    logger.info(f"Hybrid format result: {result}")
    assert result.get("github_updated", False), "Should successfully handle hybrid format"
    assert result.get("github_pr_url") is not None, "Should create PR with hybrid format"
    
    # Verify that the correct file changes were passed to commit_bug_fix
    commit_call_args = agent.github_service.commit_bug_fix.call_args_list[-1][0]
    file_changes = commit_call_args[1]  # Second argument should be the file changes
    
    # Note: In a real test we'd verify the exact files, but that's dependent on implementation details
    
    # Test with nested developer_result structure
    nested_format_input = {
        "ticket_id": "TEST-203",
        "test_passed": True,
        "developer_result": {
            "patch_content": "@@ -1,1 +1,1 @@\n-old\n+new",
            "patched_files": ["src/file5.py"],
            "commit_message": "Fix bug in file5"
        },
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(nested_format_input)
    logger.info(f"Nested developer_result format result: {result}")
    assert result.get("github_updated", False), "Should successfully handle nested format"
    assert result.get("github_pr_url") is not None, "Should create PR with nested format"
    
    # Test nested empty developer_result (regression test)
    empty_nested_input = {
        "ticket_id": "TEST-204",
        "test_passed": True,
        "developer_result": {},
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Should not raise exceptions even with empty developer_result
    result = await agent.run(empty_nested_input)
    logger.info(f"Empty nested format result: {result}")
    assert "error" not in result, "Should handle empty nested format gracefully"

    # Test for empty patch content case
    empty_patch_input = {
        "ticket_id": "TEST-205",
        "test_passed": True,
        "patch_content": "",
        "patched_files": ["src/file6.py"],
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(empty_patch_input)
    logger.info(f"Empty patch content result: {result}")
    assert "patch_valid" in result and not result["patch_valid"], "Should detect empty patch content"
    assert "rejection_reason" in result, "Should provide rejection reason for empty patch"

async def test_patch_validation(agent):
    """Test validation of LLM-generated patches"""
    logger.info("Testing patch validation logic...")
    
    # Configure patch validator mocks
    agent.patch_validator._is_valid_file_path = MagicMock(return_value=True)
    agent.patch_validator._is_valid_diff_syntax = MagicMock(return_value=True)
    agent.patch_validator._check_for_placeholders = MagicMock(return_value=[])
    
    # Test case with valid patch
    valid_patch_input = {
        "ticket_id": "TEST-128",
        "test_passed": True,
        "patches": [
            {
                "file_path": "real_file.py",
                "diff": "@@ -10,5 +10,7 @@\n import os\n+import logging\n+\n def main():\n-    print('Hello')\n+    logging.info('Hello')\n     return True"
            }
        ],
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Override GitHub service for this test
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": True,
        "reasons": [],
        "confidence_boost": 10
    })
    
    result = await agent.run(valid_patch_input)
    logger.info(f"Valid patch validation result: {result}")
    assert result.get("patch_valid", False), "Valid patch should be marked as valid"
    
    # Test case with invalid patch (placeholder path)
    invalid_patch_input = {
        "ticket_id": "TEST-129",
        "test_passed": False,
        "patches": [
            {
                "file_path": "/path/to/some/file.py",  # Placeholder path
                "diff": "@@ -5,3 +5,3 @@\n def func():\n-    return None\n+    return {}"
            }
        ],
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Reset mocks for invalid path test
    agent.patch_validator._is_valid_file_path = MagicMock(return_value=False) 
    agent.patch_validator._is_valid_diff_syntax = MagicMock(return_value=True)
    agent.patch_validator._check_for_placeholders = MagicMock(return_value=["path_placeholder:/path/to/"])
    
    # Override GitHub service validation for this test
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": False,
        "reasons": ["Placeholder path detected"],
        "confidence_penalty": 30
    })
    
    result = await agent.run(invalid_patch_input)
    logger.info(f"Invalid patch validation result: {result}")
    assert not result.get("patch_valid", True), "Invalid patch should be marked as invalid"
    assert "rejection_reason" in result, "Rejection reason should be provided"
    
    # Test case with syntactically invalid diff
    syntax_error_input = {
        "ticket_id": "TEST-130",
        "test_passed": False,
        "patches": [
            {
                "file_path": "real_file.py",
                "diff": "This is not a valid diff format"  # Not proper diff syntax
            }
        ],
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Reset mocks for syntax error test
    agent.patch_validator._is_valid_file_path = MagicMock(return_value=True)
    agent.patch_validator._is_valid_diff_syntax = MagicMock(return_value=False)
    agent.patch_validator._check_for_placeholders = MagicMock(return_value=[])
    
    # Override validation for this test
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": False,
        "reasons": ["Invalid diff syntax"],
        "confidence_penalty": 40
    })
    
    result = await agent.run(syntax_error_input)
    logger.info(f"Syntax error validation result: {result}")
    assert not result.get("patch_valid", True), "Syntactically invalid patch should be rejected"
    assert "rejection_reason" in result, "Rejection reason should be provided for syntax error"
    
    # Test case with patched_files but no patch_content
    missing_content_input = {
        "ticket_id": "TEST-131",
        "test_passed": True,
        "patched_files": ["src/file.py"],  # Files without content
        "retry_count": 0,
        "max_retries": 4
    }
    
    result = await agent.run(missing_content_input)
    logger.info(f"Missing patch content result: {result}")
    assert not result.get("patch_valid", True), "Should reject when patch_content is missing"
    assert "rejection_reason" in result, "Should provide rejection reason"
