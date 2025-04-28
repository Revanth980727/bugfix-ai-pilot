
import logging
import os
from datetime import datetime
from typing import Optional

class Logger:
    """A simple logger to track agent activities with timestamps"""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        Initialize a logger with a name and optional log file path
        
        Args:
            name: Name of the logger/agent
            log_file: Path to log file (if None, will use 'logs/{name}_{date}.log')
        """
        self.name = name
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Set up log file if not provided
        if not log_file:
            date_str = datetime.now().strftime("%Y%m%d")
            log_file = f"logs/{name}_{date_str}.log"
        
        # Configure logging
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)
    
    def error(self, message: str) -> None:
        """Log error message"""
        self.logger.error(message)
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)
    
    def debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)
        
    def start_task(self, task_name: str) -> None:
        """Log start of a task"""
        self.info(f"Starting {task_name}")
        
    def end_task(self, task_name: str, success: bool = True) -> None:
        """Log end of a task"""
        status = "successfully" if success else "with failures"
        self.info(f"Completed {task_name} {status}")
