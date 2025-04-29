
import json
import logging
from typing import Dict, List, Any, Optional
from langchain.agents import Tool
from ..agent_framework.planner_agent import PlannerAgent
from ..agent_framework.developer_agent import DeveloperAgent
from ..agent_framework.qa_agent import QAAgent
from ..agent_framework.communicator_agent import CommunicatorAgent
from .base import ticket_memory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("langchain-tools")

class AgentTools:
    """Tools for interacting with agents through LangChain"""
    
    def __init__(self):
        self.planner_agent = PlannerAgent()
        self.developer_agent = DeveloperAgent()
        self.qa_agent = QAAgent()
        self.communicator_agent = CommunicatorAgent()
    
    def run_planner_tool(self, input_string: str) -> str:
        """Run the planner agent to analyze the ticket"""
        try:
            # Parse the input as JSON
            input_data = json.loads(input_string)
            ticket_id = input_data.get("ticket_id")
            
            logger.info(f"Running planner agent for ticket {ticket_id}")
            
            # Run the planner agent
            result = self.planner_agent.process(input_data)
            
            # Store the result in memory
            ticket_memory.save_to_memory(
                ticket_id, 
                "Planner", 
                f"Analysis completed. Affected files: {result.get('affected_files', [])} Error type: {result.get('error_type', 'Unknown')}"
            )
            
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error running planner agent: {str(e)}")
            return json.dumps({"error": str(e)})
    
    def run_developer_tool(self, input_string: str) -> str:
        """Run the developer agent to generate a fix"""
        try:
            # Parse the input as JSON
            input_data = json.loads(input_string)
            ticket_id = input_data.get("ticket_id")
            attempt = input_data.get("attempt", 1)
            
            logger.info(f"Running developer agent for ticket {ticket_id} (attempt {attempt})")
            
            # Get context from memory if available
            memory_context = ticket_memory.get_memory_context(ticket_id)
            if memory_context and "context" not in input_data:
                input_data["context"] = {"memory": memory_context}
            
            # Run the developer agent
            result = self.developer_agent.process(input_data)
            
            # Store result in memory
            confidence = result.get("confidence_score", "Unknown")
            ticket_memory.save_to_memory(
                ticket_id,
                "Developer",
                f"Generated fix for attempt {attempt} with confidence score: {confidence}%"
            )
            
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error running developer agent: {str(e)}")
            return json.dumps({"error": str(e)})
    
    def run_qa_tool(self, input_string: str) -> str:
        """Run the QA agent to test the fix"""
        try:
            # Parse the input as JSON
            input_data = json.loads(input_string)
            ticket_id = input_data.get("ticket_id")
            
            logger.info(f"Running QA agent for ticket {ticket_id}")
            
            # Run the QA agent
            result = self.qa_agent.process(input_data)
            
            # Store the result in memory
            passed = "PASSED" if result.get("passed", False) else "FAILED"
            failure_summary = result.get("failure_summary", "")
            message = f"QA tests {passed}. {failure_summary if failure_summary else ''}"
            ticket_memory.save_to_memory(ticket_id, "QA", message)
            
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error running QA agent: {str(e)}")
            return json.dumps({"error": str(e)})
    
    def run_communicator_tool(self, input_string: str) -> str:
        """Run the communicator agent to update JIRA and GitHub"""
        try:
            # Parse the input as JSON
            input_data = json.loads(input_string)
            ticket_id = input_data.get("ticket_id")
            
            logger.info(f"Running communicator agent for ticket {ticket_id}")
            
            # Run the communicator agent
            result = self.communicator_agent.process(input_data)
            
            # Store the result in memory
            status = "succeeded" if result.get("communications_success", False) else "failed"
            ticket_memory.save_to_memory(ticket_id, "Communicator", f"Communications {status}")
            
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error running communicator agent: {str(e)}")
            return json.dumps({"error": str(e)})
    
    def get_agent_tools(self) -> List[Tool]:
        """Get all tools for interacting with agents"""
        return [
            Tool(
                name="PlannerAgent",
                func=self.run_planner_tool,
                description="Analyzes the bug ticket to identify affected files and error type. Input should be a JSON string with ticket_id, title, and description."
            ),
            Tool(
                name="DeveloperAgent",
                func=self.run_developer_tool,
                description="Generates code fixes based on planner analysis. Input should be a JSON string with ticket_id, affected_files, error_type, attempt, and max_attempts."
            ),
            Tool(
                name="QAAgent",
                func=self.run_qa_tool,
                description="Tests code fixes by running tests. Input should be a JSON string with ticket_id and test_command."
            ),
            Tool(
                name="CommunicatorAgent",
                func=self.run_communicator_tool,
                description="Updates JIRA and GitHub with results. Input should be a JSON string with ticket_id, test_passed, github_pr_url, retry_count, and max_retries."
            )
        ]
