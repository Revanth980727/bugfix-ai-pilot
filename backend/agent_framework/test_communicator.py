
import pytest
import logging
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock

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
    agent.jira_client.add_comment = MagicMock(return_value=True)
    agent.jira_client.update_ticket = MagicMock(return_value=True)
    
    agent.github_client = MagicMock()
    agent.github_client.create_branch = MagicMock(return_value="test-branch")
    agent.github_client.create_pull_request = MagicMock(return_value="https://github.com/org/repo/pull/1")
    agent.github_client.add_pr_comment = MagicMock(return_value=True)
    
    # Test successful case
    success_input = {
        "ticket_id": "TEST-123",
        "test_passed": True,
        "github_pr_url": "https://github.com/org/repo/pull/1",
        "retry_count": 0,
        "max_retries": 4
    }
    
    try:
        result = agent.run(success_input)
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
        "github_pr_url": "https://github.com/org/repo/pull/2",
        "retry_count": 2,
        "max_retries": 4
    }
    
    try:
        result = agent.run(failure_input)
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
    agent.github_client.create_pull_request = MagicMock(return_value=None)
    
    try:
        result = agent.run(edge_input)
        logger.info(f"Edge case result: {result}")
        
        assert result["ticket_id"] == "TEST-125"
        assert "error" in result
        
    except Exception as e:
        logger.error(f"Edge case test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_communicator_agent())
