
import logging
import os
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-utils")

# Agent service URLs
PLANNER_URL = os.getenv("PLANNER_URL", "http://planner:8001")
DEVELOPER_URL = os.getenv("DEVELOPER_URL", "http://developer:8002")
QA_URL = os.getenv("QA_URL", "http://qa:8003")
COMMUNICATOR_URL = os.getenv("COMMUNICATOR_URL", "http://communicator:8004")

async def call_planner_agent(ticket: Dict[str, Any]):
    """Send ticket information to the Planner agent"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{PLANNER_URL}/analyze",
                json=ticket
            )
            
            if response.status_code != 200:
                logger.error(f"Planner agent error: {response.status_code}")
                return None
                
            return response.json()
    except Exception as e:
        logger.error(f"Error calling Planner agent: {str(e)}")
        return None

async def call_developer_agent(planner_analysis: Dict[str, Any], attempt: int, context: Dict[str, Any] = None):
    """Send planner analysis to Developer agent"""
    try:
        payload = {
            "analysis": planner_analysis,
            "attempt": attempt
        }
        
        # Add context information (like previous QA results) if available
        if context:
            payload["context"] = context
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{DEVELOPER_URL}/generate",
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Developer agent error: {response.status_code}")
                return None
                
            return response.json()
    except Exception as e:
        logger.error(f"Error calling Developer agent: {str(e)}")
        return None

async def call_qa_agent(developer_response: Dict[str, Any]):
    """Send developer's changes to QA agent"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{QA_URL}/test",
                json=developer_response
            )
            
            if response.status_code != 200:
                logger.error(f"QA agent error: {response.status_code}")
                return None
                
            return response.json()
    except Exception as e:
        logger.error(f"Error calling QA agent: {str(e)}")
        return None

async def call_communicator_agent(ticket_id: str, diffs: List[Dict[str, Any]], 
                                test_results: List[Dict[str, Any]], commit_message: str):
    """Send results to Communicator agent"""
    try:
        payload = {
            "ticket_id": ticket_id,
            "diffs": diffs,
            "test_results": test_results,
            "commit_message": commit_message,
            "repository": "main"  # This would be configurable in a real implementation
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{COMMUNICATOR_URL}/deploy",
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Communicator agent error: {response.status_code}")
                return None
                
            return response.json()
    except Exception as e:
        logger.error(f"Error calling Communicator agent: {str(e)}")
        return None
