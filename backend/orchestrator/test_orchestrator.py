
import asyncio
import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.orchestrator import Orchestrator
from agent_framework.agent_base import AgentStatus


@pytest.fixture
def mock_jira_client():
    """Create a mock JIRA client"""
    mock = MagicMock()
    mock.get_open_bugs = AsyncMock(return_value=[
        {
            "ticket_id": "BUG-123",
            "title": "Test Bug",
            "description": "This is a test bug description"
        }
    ])
    mock.update_ticket = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_github_service():
    """Create a mock GitHub service"""
    mock = MagicMock()
    mock.create_branch = AsyncMock(return_value=True)
    mock.create_pull_request = AsyncMock(return_value="https://github.com/org/repo/pull/123")
    mock.add_pr_comment = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_planner_agent():
    """Create a mock Planner agent"""
    mock = MagicMock()
    mock.process = MagicMock(return_value={
        "ticket_id": "BUG-123",
        "affected_files": ["src/components/test.js"],
        "root_cause": "Test root cause",
        "suggested_approach": "Test approach"
    })
    mock.name = "PlannerAgent"
    mock.status = AgentStatus.SUCCESS
    return mock


@pytest.fixture
def mock_developer_agent():
    """Create a mock Developer agent"""
    mock = MagicMock()
    mock.process = MagicMock(return_value={
        "ticket_id": "BUG-123",
        "files_modified": ["src/components/test.js"],
        "patches_applied": 1,
        "diff_summary": "1 change applied"
    })
    mock.name = "DeveloperAgent"
    mock.status = AgentStatus.SUCCESS
    return mock


@pytest.fixture
def mock_qa_agent_success():
    """Create a mock QA agent that succeeds"""
    mock = MagicMock()
    mock.process = MagicMock(return_value={
        "ticket_id": "BUG-123",
        "passed": True,
        "test_results": [{"name": "test1", "status": "pass"}]
    })
    mock.name = "QAAgent"
    mock.status = AgentStatus.SUCCESS
    return mock


@pytest.fixture
def mock_qa_agent_failure():
    """Create a mock QA agent that fails"""
    mock = MagicMock()
    mock.process = MagicMock(return_value={
        "ticket_id": "BUG-123",
        "passed": False,
        "test_results": [{"name": "test1", "status": "fail"}]
    })
    mock.name = "QAAgent"
    mock.status = AgentStatus.FAILED
    return mock


@pytest.fixture
def mock_communicator_agent():
    """Create a mock Communicator agent"""
    mock = MagicMock()
    mock.process = MagicMock(return_value={
        "ticket_id": "BUG-123",
        "communications_success": True,
        "jira_updated": True,
        "github_updated": True
    })
    mock.name = "CommunicatorAgent"
    mock.status = AgentStatus.SUCCESS
    return mock


@pytest.mark.asyncio
async def test_successful_ticket_processing(
    mock_jira_client,
    mock_github_service,
    mock_planner_agent,
    mock_developer_agent,
    mock_qa_agent_success,
    mock_communicator_agent
):
    """Test successful processing of a ticket through the entire pipeline"""
    # Set up orchestrator with mocks
    orchestrator = Orchestrator()
    orchestrator.jira_client = mock_jira_client
    orchestrator.github_service = mock_github_service
    orchestrator.planner_agent = mock_planner_agent
    orchestrator.developer_agent = mock_developer_agent
    orchestrator.qa_agent = mock_qa_agent_success
    orchestrator.communicator_agent = mock_communicator_agent
    
    # Create test ticket
    test_ticket = {
        "ticket_id": "BUG-123",
        "title": "Test Bug",
        "description": "This is a test bug description"
    }
    
    # Process ticket
    await orchestrator.process_ticket(test_ticket)
    
    # Check that all agents were called
    mock_planner_agent.process.assert_called_once()
    mock_developer_agent.process.assert_called_once()
    mock_qa_agent_success.process.assert_called_once()
    mock_communicator_agent.process.assert_called_once()
    
    # Check ticket status
    assert orchestrator.active_tickets["BUG-123"]["status"] == "completed"


@pytest.mark.asyncio
async def test_retry_mechanism(
    mock_jira_client,
    mock_github_service,
    mock_planner_agent,
    mock_developer_agent,
    mock_qa_agent_failure,
    mock_communicator_agent
):
    """Test the retry mechanism for failed QA tests"""
    # Set up orchestrator with mocks
    orchestrator = Orchestrator()
    orchestrator.jira_client = mock_jira_client
    orchestrator.github_service = mock_github_service
    orchestrator.planner_agent = mock_planner_agent
    orchestrator.developer_agent = mock_developer_agent
    orchestrator.qa_agent = mock_qa_agent_failure
    orchestrator.communicator_agent = mock_communicator_agent
    
    # Mock max retries to 2 for faster test
    with patch('orchestrator.orchestrator.MAX_RETRIES', 2):
        # Create test ticket
        test_ticket = {
            "ticket_id": "BUG-123",
            "title": "Test Bug",
            "description": "This is a test bug description"
        }
        
        # Process ticket
        await orchestrator.process_ticket(test_ticket)
        
        # Check that planner was called once
        mock_planner_agent.process.assert_called_once()
        
        # Developer should be called for each retry attempt
        assert mock_developer_agent.process.call_count == 2
        
        # QA should be called for each retry attempt
        assert mock_qa_agent_failure.process.call_count == 2
        
        # Communicator should be called once for escalation
        mock_communicator_agent.process.assert_called_once()
        
        # Check ticket status
        assert orchestrator.active_tickets["BUG-123"]["status"] == "escalated"


@pytest.mark.asyncio
async def test_fetch_eligible_tickets(mock_jira_client):
    """Test fetching eligible tickets from JIRA"""
    orchestrator = Orchestrator()
    orchestrator.jira_client = mock_jira_client
    
    # Get tickets
    tickets = await orchestrator.fetch_eligible_tickets()
    
    # Check that get_open_bugs was called
    mock_jira_client.get_open_bugs.assert_called_once()
    
    # Check returned tickets
    assert len(tickets) == 1
    assert tickets[0]["ticket_id"] == "BUG-123"


if __name__ == "__main__":
    pytest.main(["-xvs", "test_orchestrator.py"])
