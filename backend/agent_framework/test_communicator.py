
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
    agent.github_service.create_fix_branch = MagicMock(return_value="test-branch")
    agent.github_service.create_pull_request = MagicMock(return_value="https://github.com/org/repo/pull/123")
    agent.github_service.add_pr_comment = MagicMock(return_value=True)
    agent.github_service.find_pr_for_branch = MagicMock(return_value={
        "number": 123,
        "url": "https://github.com/org/repo/pull/123"
    })
    agent.github_service.check_file_exists = MagicMock(return_value=True)
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": True,
        "reasons": [],
        "confidence_boost": 10
    })
    
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

async def test_patch_validation(agent):
    """Test validation of LLM-generated patches"""
    logger.info("Testing patch validation logic...")
    
    # Mock patch validation functions
    agent.validate_file_exists = MagicMock(return_value=True)
    agent.validate_diff_syntax = MagicMock(return_value=True)
    agent.check_for_placeholders = MagicMock(return_value=False)
    
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
    
    # Override validation for this test
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
    
    # Override validation for this test
    agent.github_service.validate_patch = MagicMock(return_value={
        "valid": False,
        "reasons": ["Invalid diff syntax"],
        "confidence_penalty": 40
    })
    
    result = await agent.run(syntax_error_input)
    logger.info(f"Syntax error validation result: {result}")
    assert not result.get("patch_valid", True), "Syntactically invalid patch should be rejected"
    assert "syntax_error" in result.get("rejection_reason", ""), "Syntax error should be mentioned"

if __name__ == "__main__":
    asyncio.run(test_communicator_agent())
