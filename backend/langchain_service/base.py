
import logging
from typing import Dict, List, Any, Optional
from langchain.chains import LLMChain
from langchain.llms.openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent, AgentOutputParser
from langchain.schema import AgentAction, AgentFinish
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("langchain-service")

class TicketMemory:
    """Memory manager for ticket processing workflow"""
    
    def __init__(self):
        # Initialize shared memory for all tickets
        self.memories = {}
        
    def get_memory(self, ticket_id: str) -> ConversationBufferMemory:
        """Get or create memory for a specific ticket"""
        if ticket_id not in self.memories:
            self.memories[ticket_id] = ConversationBufferMemory(memory_key="chat_history")
        return self.memories[ticket_id]
    
    def save_to_memory(self, ticket_id: str, role: str, content: str) -> None:
        """Save an interaction to memory"""
        memory = self.get_memory(ticket_id)
        memory.chat_memory.add_user_message(f"[{role}] {content}")
        
    def get_memory_context(self, ticket_id: str) -> str:
        """Get the current memory context as a string"""
        if ticket_id not in self.memories:
            return ""
        
        return self.memories[ticket_id].buffer
    
    def clear_memory(self, ticket_id: str) -> None:
        """Clear memory for a ticket when processing completes"""
        if ticket_id in self.memories:
            del self.memories[ticket_id]
            logger.info(f"Memory cleared for ticket {ticket_id}")

# Create a singleton instance
ticket_memory = TicketMemory()

class OrchestratorOutputParser(AgentOutputParser):
    """Parser for orchestrator outputs that handles agent decisions"""
    
    def parse(self, llm_output: str) -> AgentAction or AgentFinish:
        # Check if the output indicates a final decision
        if "Final Answer:" in llm_output:
            return AgentFinish(
                return_values={"output": llm_output.split("Final Answer:")[-1].strip()},
                log=llm_output
            )
        
        # Parse the action and input
        regex = r"Action: (.*?)\nAction Input: (.*)"
        match = re.search(regex, llm_output, re.DOTALL)
        
        if not match:
            return AgentFinish(
                return_values={"output": "Could not parse LLM output: " + llm_output},
                log=llm_output,
            )
            
        action = match.group(1).strip()
        action_input = match.group(2).strip()
        
        return AgentAction(tool=action, tool_input=action_input, log=llm_output)
