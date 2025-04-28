
import logging
from agent_base import Agent, AgentStatus
from qa_agent import QAAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_qa_agent():
    # Initialize the QA agent
    qa = QAAgent()
    
    # Test input
    test_input = {
        "ticket_id": "BUG-123",
        "test_command": "npm test",  # Using frontend test command for example
        "target": "src/components/auth"  # Optional target directory
    }
    
    # Run QA agent
    try:
        result = qa.process(test_input)
        logger.info(f"\nQA Agent status: {qa.status}")
        logger.info(f"Processing result: {result}")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    test_qa_agent()

