
import pytest
import logging
from datetime import datetime
from .communicator_agent import CommunicatorAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_communicator_agent():
    # Initialize agent
    agent = CommunicatorAgent()
    
    # Test successful case
    success_input = {
        "ticket_id": "TEST-123",
        "test_passed": True,
        "github_pr_url": "https://github.com/org/repo/pull/1",
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
        result = await agent.run(failure_input)
        logger.info(f"\nCommunicator Agent status: {agent.status}")
        logger.info(f"Processing result: {result}")
        
        assert result["ticket_id"] == "TEST-124"
        assert "communications_success" in result
        assert not result["test_passed"]
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_communicator_agent())

