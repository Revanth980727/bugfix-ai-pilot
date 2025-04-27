
import asyncio
import logging
from datetime import datetime
from jira_utils import fetch_jira_tickets
from ticket_processor import process_ticket, cleanup_old_tickets, active_tickets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/controller_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bugfix-controller")

async def run_controller():
    """Main controller loop that runs every 60 seconds"""
    while True:
        try:
            # Fetch new tickets from JIRA
            new_tickets = await fetch_jira_tickets()
            
            # Process each new ticket
            for ticket in new_tickets:
                # Skip if already being processed
                if ticket["ticket_id"] not in active_tickets:
                    asyncio.create_task(process_ticket(ticket))
            
            # Clean up old tickets
            await cleanup_old_tickets()
            
            # Wait for next cycle
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Controller error: {str(e)}")
            await asyncio.sleep(60)

def start_controller():
    """Start the controller loop"""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_controller())
    except KeyboardInterrupt:
        logger.info("Controller stopping due to keyboard interrupt")
    finally:
        loop.close()

if __name__ == "__main__":
    start_controller()

