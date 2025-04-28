
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
        
        # Also test fallback functionality by forcing an invalid response
        logger.info("\nTesting fallback functionality:")
        
        # Create a test version of the planner that returns invalid JSON
        class TestPlannerWithForcedFailure(PlannerAgent):
            def _query_gpt(self, prompt: str) -> str:
                # Return invalid JSON to trigger fallback
                return "This is not JSON and will trigger the fallback mechanism"
        
        test_planner = TestPlannerWithForcedFailure()
        fallback_result = test_planner.process(test_ticket)
        
        logger.info(f"Fallback result: {fallback_result}")
        logger.info(f"Is using fallback: {fallback_result.get('using_fallback', False)}")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    test_planner_agent()
