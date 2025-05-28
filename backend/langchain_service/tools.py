
import json
import logging
import os
from typing import Dict, Any
from langchain.tools import Tool

# Import agents from the backend framework
from ..agent_framework.developer_agent import DeveloperAgent
from ..agent_framework.planner_agent import PlannerAgent  
from ..agent_framework.qa_agent import QAAgent
from ..agent_framework.communicator_agent import CommunicatorAgent

logger = logging.getLogger("langchain-tools")

class AgentTools:
    """Tools for LangChain orchestrator to call individual agents"""
    
    def __init__(self):
        # Initialize agents
        self.developer_agent = DeveloperAgent()
        self.planner_agent = PlannerAgent()
        self.qa_agent = QAAgent()
        self.communicator_agent = CommunicatorAgent()
        
        logger.info("AgentTools initialized with backend framework agents")
    
    def call_planner_agent(self, input_json: str) -> str:
        """Call the planner agent with JSON input"""
        try:
            input_data = json.loads(input_json)
            result = self.planner_agent.run(input_data)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error calling planner agent: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    def call_developer_agent(self, input_json: str) -> str:
        """Call the developer agent with JSON input"""
        try:
            input_data = json.loads(input_json)
            result = self.developer_agent.run(input_data)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error calling developer agent: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    def call_qa_agent(self, input_json: str) -> str:
        """Call the QA agent with JSON input"""
        try:
            input_data = json.loads(input_json)
            result = self.qa_agent.run(input_data)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error calling QA agent: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    def call_communicator_agent(self, input_json: str) -> str:
        """Call the communicator agent with JSON input"""
        try:
            input_data = json.loads(input_json)
            result = self.communicator_agent.run(input_data)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error calling communicator agent: {e}")
            return json.dumps({"error": str(e), "success": False})
    
    def get_agent_tools(self):
        """Return LangChain tools for each agent"""
        return [
            Tool(
                name="PlannerAgent",
                description="Analyzes bug tickets and identifies affected files and error types",
                func=self.call_planner_agent
            ),
            Tool(
                name="DeveloperAgent", 
                description="Generates code fixes using unified diffs or full file replacement",
                func=self.call_developer_agent
            ),
            Tool(
                name="QAAgent",
                description="Tests generated fixes to verify they resolve the bug",
                func=self.call_qa_agent
            ),
            Tool(
                name="CommunicatorAgent",
                description="Updates GitHub and JIRA with results and creates pull requests",
                func=self.call_communicator_agent
            )
        ]
