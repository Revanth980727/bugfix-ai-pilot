
import logging
import os
from datetime import datetime
from typing import Optional
import sys
import json

class Logger:
    """A simple logger to track agent activities with timestamps"""
    
    def __init__(self, name: str, log_file: Optional[str] = None, log_level: str = None):
        """
        Initialize a logger with a name and optional log file path
        
        Args:
            name: Name of the logger/agent
            log_file: Path to log file (if None, will use 'logs/{name}_{date}.log')
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        
        # Set log level from environment or parameter or default to INFO
        log_level = log_level or os.environ.get('LOG_LEVEL', 'INFO').upper()
        numeric_level = getattr(logging, log_level, logging.INFO)
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Set up log file if not provided
        if not log_file:
            date_str = datetime.now().strftime("%Y%m%d")
            log_file = f"logs/{name}_{date_str}.log"
        
        # Configure logging
        self.logger = logging.getLogger(name)
        self.logger.setLevel(numeric_level)
        
        # Clear existing handlers if any (useful for testing/reloading)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        
        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)  # Use stdout instead of stderr
        console_handler.setLevel(numeric_level)
        
        # Create formatter
        formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
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
        
    def critical(self, message: str) -> None:
        """Log critical message"""
        self.logger.critical(message)
    
    def start_task(self, task_name: str) -> None:
        """Log start of a task"""
        self.info(f"Starting {task_name}")
        
    def end_task(self, task_name: str, success: bool = True) -> None:
        """Log end of a task"""
        status = "successfully" if success else "with failures"
        self.info(f"Completed {task_name} {status}")
        
    def log_dict(self, message: str, data: dict) -> None:
        """Log a dictionary as JSON"""
        json_str = json.dumps(data, indent=2)
        self.info(f"{message}: {json_str}")
