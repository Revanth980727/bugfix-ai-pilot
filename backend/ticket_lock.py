
"""
Module for managing ticket locks to prevent duplicate processing
"""
import os
import logging
import asyncio
import tempfile
import time
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger("ticket-lock")

class TicketLockManager:
    """Class for managing ticket locks"""
    
    def __init__(self, lock_dir: Optional[str] = None):
        """
        Initialize the lock manager
        
        Args:
            lock_dir: Directory to store lock files. If None, a system temp directory is used.
        """
        if lock_dir:
            self.lock_dir = lock_dir
            os.makedirs(lock_dir, exist_ok=True)
        else:
            # Use system temp directory
            self.lock_dir = os.path.join(tempfile.gettempdir(), "ticket_locks")
            os.makedirs(self.lock_dir, exist_ok=True)
            
        logger.info(f"Using lock directory: {self.lock_dir}")
    
    async def acquire_lock(self, ticket_id: str, timeout: int = 0) -> bool:
        """
        Try to acquire a lock for a ticket
        
        Args:
            ticket_id: ID of the ticket to lock
            timeout: Seconds to wait for lock (0 means don't wait)
            
        Returns:
            bool: True if lock was acquired, False otherwise
        """
        lock_file = os.path.join(self.lock_dir, f"{ticket_id}.lock")
        
        # Check if lock file exists and is not stale
        start_time = time.time()
        while True:
            if not os.path.exists(lock_file):
                try:
                    # Create lock file with current timestamp
                    with open(lock_file, 'w') as f:
                        f.write(f"{datetime.now().isoformat()}\n")
                        f.write(f"{os.getpid()}\n")
                    logger.info(f"Lock acquired for ticket {ticket_id}")
                    return True
                except Exception as e:
                    logger.error(f"Error creating lock file for {ticket_id}: {str(e)}")
                    return False
            else:
                # Check if lock is stale (older than 1 hour)
                try:
                    modified_time = os.path.getmtime(lock_file)
                    if time.time() - modified_time > 3600:  # 1 hour
                        logger.warning(f"Found stale lock for {ticket_id}, overriding")
                        await self.release_lock(ticket_id)
                        continue
                except Exception as e:
                    logger.error(f"Error checking lock file for {ticket_id}: {str(e)}")
            
            # If we've waited long enough, give up
            if timeout > 0 and (time.time() - start_time) > timeout:
                logger.warning(f"Timeout waiting for lock on ticket {ticket_id}")
                return False
                
            # Wait a bit before checking again
            if timeout > 0:
                await asyncio.sleep(1)
            else:
                break
                
        logger.info(f"Could not acquire lock for ticket {ticket_id}")
        return False
    
    async def release_lock(self, ticket_id: str) -> bool:
        """
        Release a lock for a ticket
        
        Args:
            ticket_id: ID of the ticket to unlock
            
        Returns:
            bool: True if lock was released, False otherwise
        """
        lock_file = os.path.join(self.lock_dir, f"{ticket_id}.lock")
        
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info(f"Lock released for ticket {ticket_id}")
                return True
            else:
                logger.warning(f"No lock file found for ticket {ticket_id}")
                return False
        except Exception as e:
            logger.error(f"Error releasing lock for {ticket_id}: {str(e)}")
            return False
    
    async def cleanup_stale_locks(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale lock files
        
        Args:
            max_age_hours: Maximum age of lock files in hours
            
        Returns:
            int: Number of stale locks cleaned up
        """
        cleaned = 0
        try:
            for filename in os.listdir(self.lock_dir):
                if filename.endswith(".lock"):
                    filepath = os.path.join(self.lock_dir, filename)
                    modified_time = os.path.getmtime(filepath)
                    if time.time() - modified_time > max_age_hours * 3600:
                        os.remove(filepath)
                        cleaned += 1
                        logger.info(f"Cleaned up stale lock: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning up stale locks: {str(e)}")
            
        return cleaned
    
    async def get_active_locks(self) -> dict:
        """
        Get a list of all active locks
        
        Returns:
            dict: Dictionary mapping ticket IDs to lock information
        """
        locks = {}
        try:
            for filename in os.listdir(self.lock_dir):
                if filename.endswith(".lock"):
                    ticket_id = filename[:-5]  # Remove .lock extension
                    filepath = os.path.join(self.lock_dir, filename)
                    modified_time = os.path.getmtime(filepath)
                    
                    # Read PID from lock file if available
                    pid = None
                    try:
                        with open(filepath, 'r') as f:
                            lines = f.readlines()
                            if len(lines) >= 2:
                                pid = int(lines[1].strip())
                    except:
                        pass
                    
                    locks[ticket_id] = {
                        "locked_since": datetime.fromtimestamp(modified_time).isoformat(),
                        "age_seconds": int(time.time() - modified_time),
                        "pid": pid
                    }
        except Exception as e:
            logger.error(f"Error getting active locks: {str(e)}")
            
        return locks
