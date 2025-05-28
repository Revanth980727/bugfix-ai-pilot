
#!/usr/bin/env python3
"""
Legacy Agent Controller - now redirects to the new backend framework
"""

import sys
import os
import json
import logging

# Add the backend directory to the path to import the new framework
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    # Import the new agent framework
    from agent_framework.developer_agent import DeveloperAgent
    from agent_framework.planner_agent import PlannerAgent
    from agent_framework.qa_agent import QAAgent
    from agent_framework.communicator_agent import CommunicatorAgent
    
    print("Successfully imported agents from new backend framework")
except ImportError as e:
    print(f"Warning: Could not import from new backend framework: {e}")
    # Fallback to legacy imports if needed
    from developer_agent_legacy import DeveloperAgent as LegacyDeveloperAgent
    from planner_agent import PlannerAgent
    from qa_agent import QAAgent
    from communicator_agent import CommunicatorAgent
    
    # Use legacy developer agent as fallback
    DeveloperAgent = LegacyDeveloperAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_controller")

def run_agent(agent_type: str, input_data: dict) -> dict:
    """
    Run a specific agent with the given input data
    
    Args:
        agent_type: Type of agent to run ('developer', 'planner', 'qa', 'communicator')
        input_data: Input data for the agent
        
    Returns:
        Dictionary with agent results
    """
    try:
        if agent_type == 'developer':
            agent = DeveloperAgent()
        elif agent_type == 'planner':
            agent = PlannerAgent()
        elif agent_type == 'qa':
            agent = QAAgent()
        elif agent_type == 'communicator':
            agent = CommunicatorAgent()
        else:
            return {"error": f"Unknown agent type: {agent_type}"}
        
        result = agent.run(input_data)
        logger.info(f"Agent {agent_type} completed with success: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error running {agent_type} agent: {str(e)}")
        return {"error": f"Error running {agent_type} agent: {str(e)}", "success": False}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python agent_controller.py <agent_type> <input_json>")
        sys.exit(1)
    
    agent_type = sys.argv[1]
    input_json = sys.argv[2]
    
    try:
        input_data = json.loads(input_json)
        result = run_agent(agent_type, input_data)
        print(json.dumps(result, indent=2))
    except json.JSONDecodeError as e:
        print(f"Error parsing input JSON: {e}")
        sys.exit(1)
