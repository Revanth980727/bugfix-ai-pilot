
#!/usr/bin/env python3
import asyncio
import logging
import sys
import os
import json

# Add the parent directory to the path so we can import our package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("jira-service")

# Import after setting up paths
from jira_service.jira_service import main
from langchain_service.base import ticket_memory

if __name__ == "__main__":
    try:
        logger.info("Starting JIRA service")
        
        # Set environment variable to indicate we're in the JIRA service
        os.environ["SERVICE_NAME"] = "jira_service"
        
        # Ensure debug logs directory exists
        os.makedirs("debug_logs", exist_ok=True)
        
        # Initialize ticket memory system
        logger.info("Initializing ticket memory system")
        
        # Run the service
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Service stopped by user")
    except Exception as e:
        logging.error(f"Service failed with error: {e}")
        # Log detailed traceback for debugging
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
