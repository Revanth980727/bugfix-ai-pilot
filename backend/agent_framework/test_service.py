
import logging
from agent_base import Agent, AgentStatus
from planner_agent import PlannerAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_planner_agent():
    # Initialize the planner
    planner = PlannerAgent()
    
    # Test input
    test_ticket = {
        "ticket_id": "BUG-123",
        "title": "Fix login error in AuthService.tsx",
        "description": """
        When logging in on mobile devices, the handleLogin function in src/components/auth/AuthService.tsx
        throws an error. Stack trace shows:
        Error: Cannot read property 'data' of undefined
        
        This affects the following files:
        - src/components/auth/AuthService.tsx
        - src/utils/validation.ts
        - src/api/loginApi.ts
        
        The LoginComponent and ValidationHelper modules need to be checked.
        """
    }
    
    # Run analysis
    try:
        result = planner.process(test_ticket)
        logger.info(f"\nPlanner status: {planner.status}")
        logger.info(f"Analysis result: {result}")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    test_planner_agent()

