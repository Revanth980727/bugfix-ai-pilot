import json
import logging
import os
import time
from typing import Dict, Any, List

from langchain.schema import AgentAction, AgentFinish
from langchain.agents import AgentExecutor, LLMSingleActionAgent
from langchain.prompts import PromptTemplate
from langchain.llms.openai import OpenAI
from langchain.memory import ConversationBufferMemory

from .base import OrchestratorOutputParser, ticket_memory
from .tools import AgentTools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("langchain-orchestrator")

# QA agent lock management with timestamps to detect stale locks 
qa_locks = {}
QA_LOCK_TIMEOUT = 300  # 5 minutes in seconds

def acquire_qa_lock(ticket_id: str, orchestrator_id: str) -> bool:
    """Attempt to acquire a lock for running QA tests on a ticket"""
    current_time = time.time()
    
    # Check if there's an existing lock
    if ticket_id in qa_locks:
        lock_info = qa_locks[ticket_id]
        lock_age = current_time - lock_info['timestamp']
        
        # If lock is stale or held by same orchestrator, allow it
        if lock_age > QA_LOCK_TIMEOUT:
            logger.warning(f"Found stale QA lock for ticket {ticket_id}, replacing it")
        elif lock_info['orchestrator_id'] == orchestrator_id:
            logger.info(f"Orchestrator {orchestrator_id} already has QA lock for ticket {ticket_id}")
            return True
        else:
            logger.warning(f"QA tests for ticket {ticket_id} already in progress by orchestrator {lock_info['orchestrator_id']}")
            return False
    
    # Set new lock
    qa_locks[ticket_id] = {
        'orchestrator_id': orchestrator_id,
        'timestamp': current_time
    }
    logger.info(f"Acquired QA lock for ticket {ticket_id} by orchestrator {orchestrator_id}")
    return True

def release_qa_lock(ticket_id: str, orchestrator_id: str) -> bool:
    """Release a lock if it's held by the specified orchestrator"""
    if ticket_id in qa_locks and qa_locks[ticket_id]['orchestrator_id'] == orchestrator_id:
        del qa_locks[ticket_id]
        logger.info(f"Released QA lock for ticket {ticket_id} by orchestrator {orchestrator_id}")
        return True
    return False

class LangChainOrchestrator:
    """Orchestrator that uses LangChain to coordinate the workflow between agents"""
    
    def __init__(self, llm_model="gpt-4o", temperature=0.0):
        """Initialize the orchestrator with specified LLM model and temperature"""
        try:
            # Initialize the agent tools
            self.tools = AgentTools().get_agent_tools()
            
            # Initialize the LLM
            self.llm = OpenAI(temperature=temperature, model=llm_model)
            logger.info(f"Initialized LLM with model {llm_model}")
            
            # Initialize the agent with prompt and tools
            self.agent = self._create_agent()
            
            # Initialize the agent executor
            self.executor = AgentExecutor.from_agent_and_tools(
                agent=self.agent,
                tools=self.tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=15
            )
            
            # Default confidence threshold for escalations
            self.confidence_threshold = float(os.environ.get("CONFIDENCE_THRESHOLD", "70"))
            logger.info(f"Using confidence threshold: {self.confidence_threshold}%")
            
            logger.info("LangChain orchestrator initialized successfully")
        
        except Exception as e:
            logger.error(f"Error initializing LangChain orchestrator: {e}")
            raise
    
    def _create_agent(self) -> LLMSingleActionAgent:
        """Create the LangChain agent with tools and prompt"""
        prompt_template = """
        You are an AI orchestrator responsible for fixing software bugs. You coordinate a team of specialized agents to 
        analyze and fix bug tickets. You maintain context throughout the process and make decisions based on results.
        
        Current ticket: {ticket_id}
        
        Previously known information:
        {chat_history}
        
        Workflow steps:
        1. Call the PlannerAgent to analyze the bug and identify affected files & error type
        2. Call the DeveloperAgent to generate a fix (may require multiple attempts)
        3. Call the QAAgent to test if the fix resolves the bug
        4. Call the CommunicatorAgent to update GitHub and JIRA
        5. If tests fail after max attempts, escalate to human developers
        
        Current task: {input}
        
        Available tools:
        {tools}
        
        Follow these steps:
        1. Analyze the task and determine which agent is needed
        2. Call the appropriate agent with the needed information
        3. Evaluate the result and decide next steps
        4. Only move to the next workflow step when the current one is complete
        5. When the full workflow is complete, provide a "Final Answer:" with a summary
        
        IMPORTANT: Track the success/failure status from each agent consistently. When an agent reports a failure or escalation,
        ensure this status is passed to subsequent agents. The DeveloperAgent's success status should be verified by QAAgent 
        before proceeding with CommunicatorAgent.
        
        {agent_scratchpad}
        """
        
        prompt = PromptTemplate.from_template(template=prompt_template)
        
        tool_names = [tool.name for tool in self.tools]
        
        return LLMSingleActionAgent(
            llm_chain=prompt,
            output_parser=OrchestratorOutputParser(),
            allowed_tools=tool_names,
            stop=["\nObservation:"]
        )
    
    def process_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a bug ticket using the LangChain agent workflow"""
        try:
            ticket_id = ticket_data.get("ticket_id")
            title = ticket_data.get("title", "")
            description = ticket_data.get("description", "")
            
            if not ticket_id:
                logger.error("Missing ticket ID")
                return {"error": "Missing ticket ID"}
            
            logger.info(f"Processing ticket {ticket_id}")
            
            # Create input for the agent
            input_data = {
                "ticket_id": ticket_id,
                "title": title,
                "description": description
            }
            
            # Get memory for the ticket
            memory = ticket_memory.get_memory(ticket_id)
            
            # Execute the agent workflow
            result = self.executor.run(
                input=json.dumps(input_data),
                chat_history=memory.buffer if memory else ""
            )
            
            # Clean up memory when done (optional)
            # ticket_memory.clear_memory(ticket_id)
            
            logger.info(f"Completed processing ticket {ticket_id}")
            return {"result": result}
            
        except Exception as e:
            logger.error(f"Error processing ticket: {e}")
            return {"error": str(e)}
    
    def run_agent_step(self, agent_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific agent step in the workflow"""
        try:
            # Generate a unique orchestrator ID if needed
            orchestrator_id = input_data.get("orchestrator_id", f"langchain-{id(self)}")
            ticket_id = input_data.get("ticket_id", "unknown")
            
            # Find the tool with matching name
            agent_tool = next((tool for tool in self.tools if tool.name == agent_name), None)
            
            if not agent_tool:
                logger.error(f"Unknown agent: {agent_name}")
                return {"error": f"Unknown agent: {agent_name}", "success": False}
            
            # Log the input data to help debug status flag issues
            logger.info(f"Running agent {agent_name} with input: {json.dumps(input_data)[:200]}...")
            
            # Check for success/failure flags from previous agents
            if "success" in input_data and input_data["success"] is False:
                logger.warning(f"Previous agent reported failure, but still running {agent_name}")
            
            # Special handling for QAAgent to implement locking
            if agent_name == "QAAgent":
                # Try to acquire a lock for this QA run
                if not acquire_qa_lock(ticket_id, orchestrator_id):
                    logger.warning(f"QA tests already in progress for {ticket_id} by another orchestrator")
                    return {
                        "error": "Another orchestrator is already running QA tests for this ticket",
                        "success": False,
                        "skipped_due_to_lock": True
                    }
                
                try:
                    # Special handling for QAAgent to correctly structure developer results
                    if "developer_result" not in input_data and "patched_code" in input_data:
                        # Move developer output into developer_result field
                        developer_result = {
                            key: value for key, value in input_data.items() 
                            if key in ["patched_code", "patched_files", "confidence_score", "test_code", "success"]
                        }
                        # Create new input with developer_result field
                        qa_input = {
                            "ticket_id": input_data.get("ticket_id", ""),
                            "test_command": input_data.get("test_command", os.environ.get("TEST_COMMAND", "python -m pytest")),
                            "developer_result": developer_result,
                            "orchestrator_id": orchestrator_id
                        }
                        logger.info(f"Restructured QA input to include developer_result: {json.dumps(qa_input)[:200]}...")
                        input_data = qa_input
                    
                    # Execute the tool with the input data
                    result = agent_tool.func(json.dumps(input_data))
                    
                    # Parse the result back to a dictionary
                    result_dict = json.loads(result)
                    
                    return result_dict
                finally:
                    # Always release the lock when done
                    release_qa_lock(ticket_id, orchestrator_id)
            
            # Special handling for the patch_mode parameter when running DeveloperAgent
            if agent_name == "DeveloperAgent" and "patch_mode" not in input_data:
                patch_mode = os.environ.get("PATCH_MODE", "line-by-line")
                input_data["patch_mode"] = patch_mode
                logger.info(f"Setting patch_mode to {patch_mode} for DeveloperAgent")
            
            # Execute the tool with the input data
            result = agent_tool.func(json.dumps(input_data))
            
            # Parse the result back to a dictionary
            result_dict = json.loads(result)
            
            # Validate developer output if applicable
            if agent_name == "DeveloperAgent":
                if not self._validate_developer_output(result_dict):
                    logger.error("Developer output validation failed")
                    result_dict["success"] = False
                    return result_dict
            
            # Additional validation for Communicator Agent
            if agent_name == "CommunicatorAgent":
                if not self._validate_communicator_input(input_data, result_dict):
                    logger.error("Cannot proceed with communicator - validation failed")
                    result_dict["success"] = False
                    return result_dict
            
            # Log the result status
            if "success" in result_dict:
                logger.info(f"Agent {agent_name} completed with success={result_dict['success']}")
            else:
                logger.warning(f"Agent {agent_name} did not report success/failure status")
                # Set default success status if missing
                result_dict["success"] = True
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error running agent {agent_name}: {e}")
            
            # Release QA lock if this was a QA agent that failed
            if agent_name == "QAAgent":
                release_qa_lock(input_data.get("ticket_id", "unknown"), 
                               input_data.get("orchestrator_id", f"langchain-{id(self)}"))
                
            return {"error": str(e), "success": False}
            
    def _validate_developer_output(self, result: Dict[str, Any]) -> bool:
        """
        Validate that developer output meets the required structure before proceeding
        
        Args:
            result: Result dictionary from developer agent
            
        Returns:
            Boolean indicating if output is valid
        """
        # Check if confidence score is too low
        confidence_score = result.get("confidence_score", 0)
        if confidence_score <= 0:
            logger.error(f"Developer confidence score is too low: {confidence_score}")
            result["error"] = f"Confidence score is too low: {confidence_score}"
            return False
            
        # Check if patched_code is empty
        patched_code = result.get("patched_code", {})
        if not patched_code:
            logger.error("Developer patched_code is empty")
            result["error"] = "Generated patch is empty"
            return False
            
        # Check if patched_files is empty
        patched_files = result.get("patched_files", [])
        if not patched_files:
            logger.error("Developer patched_files is empty")
            result["error"] = "No files were patched"
            return False
            
        return True
            
    def _validate_communicator_input(self, input_data: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Validate that inputs to communicator meet requirements before proceeding
        
        Args:
            input_data: Input data to communicator
            result: Result from communicator
            
        Returns:
            Boolean indicating if input is valid
        """
        # Check if PR was successfully created
        pr_created = result.get("pr_created", False)
        
        # Check if QA passed
        qa_passed = input_data.get("qa_result", {}).get("passed", False)
        
        # Check confidence score
        confidence_score = input_data.get("developer_result", {}).get("confidence_score", 0)
        
        # Only set JIRA to "Done" if all conditions are met
        if not pr_created:
            logger.warning("Cannot mark JIRA as Done - PR was not created")
            return False
            
        if not qa_passed:
            logger.warning("Cannot mark JIRA as Done - QA tests did not pass")
            return False
            
        if confidence_score < self.confidence_threshold:
            logger.warning(f"Cannot mark JIRA as Done - Confidence score {confidence_score} below threshold {self.confidence_threshold}")
            return False
            
        logger.info("All criteria met for communicator to update JIRA to Done status")
        return True
