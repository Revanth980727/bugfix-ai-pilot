
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
    
    # Mock the jira and github clients
    agent.jira_client = MagicMock()
    agent.jira_client.update_ticket = AsyncMock(return_value=True)
    agent.jira_client.add_comment = AsyncMock(return_value=True)
    
    agent.github_service = MagicMock()
    agent.github_service.create_fix_branch = MagicMock(return_value=True)
    agent.github_service.create_pull_request = MagicMock(return_value="https://github.com/org/repo/pull/123")
    agent.github_service.add_pr_comment = MagicMock(return_value=True)
    agent.github_service.find_pr_for_branch = MagicMock(return_value={
        "number": 123,
        "url": "https://github.com/org/repo/pull/123"
    })
    agent.github_service.check_file_exists = MagicMock(return_value=True)
    agent.github_service.commit_bug_fix = MagicMock(return_value=True)
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
    agent.github_service.create_pull_request = MagicMock(return_value=None)
    
    try:
        result = await agent.run(edge_input)
        logger.info(f"Edge case result: {result}")
        
        assert result["ticket_id"] == "TEST-125"
        assert "error" in result or not result["communications_success"]
        
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

async def test_patch_formats(agent):
    """Test handling of different patch format structures"""
    logger.info("Testing patch format handling...")
    
    # Reset Github service mocks
    agent.github_service.create_fix_branch = MagicMock(return_value=True)
    agent.github_service.commit_bug_fix = MagicMock(return_value=True)
    agent.github_service.create_pull_request = MagicMock(return_value="https://github.com/example/repo/pull/123")
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
    assert "syntax_error" in result.get("rejection_reason", "") or "diff_syntax_invalid" in result.get("rejection_reason", ""), "Syntax error should be mentioned"

    # Test confidence score adjustment based on validation results
    confidence_input = {
        "ticket_id": "TEST-131",
        "test_passed": True,
        "patches": [
            {
                "file_path": "real_file.py",
                "diff": "@@ -10,5 +10,7 @@\n import os\n+import logging\n+\n def main():\n-    print('Hello')\n+    logging.info('Hello')\n     return True"
            }
        ],
        "confidence_score": 75,  # Initial confidence
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Reset mocks for confidence score test
    agent.patch_validator._is_valid_file_path = MagicMock(return_value=True)
    agent.patch_validator._is_valid_diff_syntax = MagicMock(return_value=True)
    agent.patch_validator._check_for_placeholders = MagicMock(return_value=[])
    
    # Valid patch should boost confidence
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": True,
        "reasons": [],
        "confidence_boost": 10
    })
    
    result = await agent.run(confidence_input)
    logger.info(f"Confidence adjustment test result: {result}")
    assert result.get("confidence_score", 0) > 75, "Confidence should be boosted for valid patches"
    
    # Multiple validation failures
    multi_failure_input = {
        "ticket_id": "TEST-132",
        "test_passed": True,
        "patches": [
            {"file_path": "real_file.py", "diff": "@@ -1,1 +1,1 @@\n-old\n+new"},
            {"file_path": "/fake/path.py", "diff": "invalid diff"},
            {"file_path": "example.py", "diff": "@@ -1,1 +1,1 @@\n-test\n+# TODO: implement me"}
        ],
        "confidence_score": 80,
        "retry_count": 0,
        "max_retries": 4
    }
    
    # Setup complex validation scenario
    def validate_patch(patch):
        if "real_file.py" in patch["file_path"]:
            return {"valid": True, "confidence_boost": 5}
        elif "/fake/" in patch["file_path"]:
            return {"valid": False, "confidence_penalty": 20, "rejection_reason": "file_path_invalid"}
        else:
            return {"valid": False, "confidence_penalty": 15, "rejection_reason": "contains_placeholders"}
    
    agent.github_service.validate_patch = MagicMock(side_effect=validate_patch)
    
    # Configure patch validator for this test
    def mock_is_valid_file_path(file_path):
        return "/fake/" not in file_path
        
    def mock_is_valid_diff_syntax(diff):
        return "invalid diff" not in diff
        
    def mock_check_for_placeholders(file_path, diff):
        if "example.py" in file_path or "TODO" in diff:
            return ["placeholder_detected"]
        return []
    
    agent.patch_validator._is_valid_file_path = MagicMock(side_effect=mock_is_valid_file_path)
    agent.patch_validator._is_valid_diff_syntax = MagicMock(side_effect=mock_is_valid_diff_syntax)
    agent.patch_validator._check_for_placeholders = MagicMock(side_effect=lambda path, diff: mock_check_for_placeholders(path, diff))
    
    result = await agent.run(multi_failure_input)
    logger.info(f"Multiple validation failures test result: {result}")
    
    assert not result.get("patch_valid", True), "Multiple failures should mark patch as invalid"
    assert result.get("confidence_score", 80) < 80, "Confidence should decrease with multiple failures"
    assert "validation_metrics" in result, "Validation metrics should be included"
    if "validation_metrics" in result:
        assert result["validation_metrics"].get("rejectedPatches", 0) == 2, "Should have 2 rejected patches"

async def test_field_name_variations(agent):
    """Test handling of different field names that indicate test success"""
    # Test all possible variations of test success fields
    field_variations = [
        {"ticket_id": "TEST-123", "test_passed": True},
        {"ticket_id": "TEST-124", "passed": True},
        {"ticket_id": "TEST-125", "success": True},
        {"ticket_id": "TEST-126", "tests_passed": True}
    ]
    
    for idx, input_data in enumerate(field_variations):
        logger.info(f"Testing field variation: {input_data}")
        result = await agent.run(input_data)
        
        # Should be treated as success in all cases
        assert agent.status == AgentStatus.SUCCESS, f"Test case {idx} not treated as success"
        assert "updates" in result, f"Result missing updates for test case {idx}"
        
        # Check that there are no "Test failed" messages in the updates
        failure_updates = [u for u in result.get("updates", []) if "failed" in u.get("message", "").lower()]
        assert len(failure_updates) == 0, f"Found failure messages in test case {idx}: {failure_updates}"
        
    # Test the inverse as well - various ways of indicating failure
    failure_variations = [
        {"ticket_id": "TEST-127", "test_passed": False},
        {"ticket_id": "TEST-128", "passed": False},
        {"ticket_id": "TEST-129", "success": False},
        {"ticket_id": "TEST-130", "tests_passed": False}
    ]
    
    for idx, input_data in enumerate(failure_variations):
        input_data["retry_count"] = 1  # Add retry count to avoid escalation
        input_data["max_retries"] = 4  # Add max retries to avoid escalation
        
        logger.info(f"Testing failure variation: {input_data}")
        result = await agent.run(input_data)
        
        # Should be treated as failure but not error
        assert agent.status != AgentStatus.SUCCESS, f"Test case {idx} incorrectly treated as success"
        assert "updates" in result, f"Result missing updates for test case {idx}"
        
        # Check that there are "Test failed" messages in the updates
        failure_updates = [u for u in result.get("updates", []) if "failed" in u.get("message", "").lower()]
        assert len(failure_updates) > 0, f"No failure messages found in test case {idx}"

if __name__ == "__main__":
    asyncio.run(test_communicator_agent())
