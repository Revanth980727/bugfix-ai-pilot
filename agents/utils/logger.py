import logging
import os
from datetime import datetime
import traceback
import sys
import importlib.util
from typing import Dict, Any, Optional

class Logger:
    """Enhanced logging utility for agents"""
    
    def __init__(self, name, log_to_file=True):
        """
        Initialize logger with name
        
        Args:
            name: Name for the logger
            log_to_file: Whether to log to a file (in addition to console)
        """
        self.name = name
        
        # Create logger with appropriate name
        self.logger = logging.getLogger(name)
        
        # Only add handlers if they don't exist
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Add formatter to console handler
            console_handler.setFormatter(formatter)
            
            # Add console handler to logger
            self.logger.addHandler(console_handler)
            
            # Add file handler if requested
            if log_to_file:
                # Create logs directory if it doesn't exist
                os.makedirs("logs", exist_ok=True)
                
                # Create file handler
                log_file = f"logs/{name}_{datetime.now().strftime('%Y%m%d')}.log"
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(logging.INFO)
                file_handler.setFormatter(formatter)
                
                # Add file handler to logger
                self.logger.addHandler(file_handler)
        
        # Keep track of current task for timing
        self.current_task = None
        self.task_start_time = None
    
    def start_task(self, task_name):
        """
        Start timing a task
        
        Args:
            task_name: Name of the task to time
        """
        self.current_task = task_name
        self.task_start_time = datetime.now()
        self.logger.info(f"Starting task: {task_name}")
    
    def end_task(self, task_name, success=True):
        """
        End timing a task and log the duration
        
        Args:
            task_name: Name of the task that was timed
            success: Whether the task completed successfully
        """
        if self.task_start_time and self.current_task == task_name:
            duration = datetime.now() - self.task_start_time
            status = "completed successfully" if success else "failed"
            self.logger.info(f"Task {task_name} {status} in {duration.total_seconds():.2f} seconds")
            self.current_task = None
            self.task_start_time = None
    
    def debug(self, message):
        """Log a debug message"""
        self.logger.debug(message)
    
    def info(self, message):
        """Log an info message"""
        self.logger.info(message)
    
    def warning(self, message):
        """Log a warning message"""
        self.logger.warning(message)
    
    def error(self, message, exc_info=None):
        """
        Log an error message, optionally with exception info
        
        Args:
            message: Error message to log
            exc_info: Boolean or exception to include stack trace
        """
        if exc_info is True:
            # Include the stack trace in the log
            self.logger.error(f"{message}\n{traceback.format_exc()}")
        else:
            self.logger.error(message)

# Define a custom error class directly in the logger module to remove the dependency on backend
class GitHubOperationError(Exception):
    """Custom exception for GitHub operation errors with metadata"""
    
    def __init__(self, message: str, operation: str, metadata: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None, error_code: str = "GITHUB_ERROR"):
        self.message = message
        self.operation = operation
        self.metadata = metadata or {}
        self.original_exception = original_exception
        self.error_code = error_code
        
        # Construct a detailed message
        detailed_message = f"GitHub {operation} error: {message}"
        if original_exception:
            detailed_message += f" (Original error: {str(original_exception)})"
            
        super().__init__(detailed_message)
