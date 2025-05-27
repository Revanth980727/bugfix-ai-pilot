
"""
Utility for handling structured error information in agent operations
"""
import logging
from typing import Dict, Any, Optional

# Configure logger
logger = logging.getLogger("error-utils")

class ErrorCodes:
    """Constants for error codes used across the system"""
    # GitHub errors
    GITHUB_PATCH_FAILED = "PATCH_FAILED"
    GITHUB_COMMIT_EMPTY = "COMMIT_EMPTY" 
    GITHUB_VALIDATION_FAILED = "VALIDATION_FAILED"
    GITHUB_FILE_NOT_FOUND = "FILE_NOT_FOUND"
    GITHUB_TEST_MODE = "TEST_MODE_REQUIRED"
    GITHUB_PERMISSION_DENIED = "PERMISSION_DENIED"
    
    # Agent errors
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    AGENT_UNKNOWN_ERROR = "AGENT_UNKNOWN_ERROR"
    AGENT_INVALID_RESPONSE = "AGENT_INVALID_RESPONSE"
    AGENT_CONTEXT_MISSING = "AGENT_CONTEXT_MISSING"
    
    # Jira errors
    JIRA_CONNECTION_ERROR = "JIRA_CONNECTION_ERROR"
    JIRA_AUTHENTICATION_ERROR = "JIRA_AUTHENTICATION_ERROR"
    JIRA_TICKET_NOT_FOUND = "JIRA_TICKET_NOT_FOUND"
    
    # General errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

def format_error(code: str, message: str, file_path: Optional[str] = None, 
                suggested_action: Optional[str] = None, 
                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a structured error object for consistent error reporting
    
    Args:
        code: Error code from ErrorCodes constants
        message: Error message
        file_path: Path to the file that caused the error (if applicable)
        suggested_action: Suggested remedy for the user
        metadata: Additional error metadata
        
    Returns:
        Structured error dictionary
    """
    error = {
        'code': code,
        'message': message
    }
    
    if file_path:
        error['file_path'] = file_path
        
    if suggested_action:
        error['suggested_action'] = suggested_action
        
    if metadata:
        error['metadata'] = metadata
        
    return error

def log_error(logger: logging.Logger, error_code: str, message: str, 
             file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Log an error and return structured error information
    
    Args:
        logger: Logger to use for logging
        error_code: Error code from ErrorCodes constants
        message: Error message
        file_path: Path to the file that caused the error (if applicable)
        metadata: Additional error metadata
        
    Returns:
        Structured error dictionary
    """
    # Format the log message
    log_message = f"[{error_code}] {message}"
    if file_path:
        log_message += f" (File: {file_path})"
        
    # Log the error
    logger.error(log_message)
    if metadata:
        logger.error(f"Error metadata: {metadata}")
        
    # Create and return structured error
    return format_error(error_code, message, file_path, metadata=metadata)

def translate_error_to_user_message(error: Dict[str, Any]) -> str:
    """
    Translate a structured error into a user-friendly message
    
    Args:
        error: Structured error dictionary
        
    Returns:
        User-friendly error message
    """
    if not isinstance(error, dict):
        return "An unknown error occurred"
        
    code = error.get('code', 'UNKNOWN_ERROR')
    message = error.get('message', 'An error occurred')
    file_path = error.get('file_path')
    suggested_action = error.get('suggested_action')
    
    # Build user-friendly message based on error code
    if code == ErrorCodes.GITHUB_PATCH_FAILED:
        user_message = f"Failed to apply code changes"
        if file_path:
            user_message += f" to {file_path}"
    elif code == ErrorCodes.GITHUB_COMMIT_EMPTY:
        user_message = "No changes were detected in the patch"
    elif code == ErrorCodes.GITHUB_FILE_NOT_FOUND:
        user_message = f"Could not find the file"
        if file_path:
            user_message += f" {file_path}"
    elif code == ErrorCodes.GITHUB_TEST_MODE:
        user_message = "This operation is only allowed in test mode"
    elif code == ErrorCodes.JIRA_TICKET_NOT_FOUND:
        user_message = "The ticket couldn't be found in Jira"
    else:
        user_message = message
        
    # Add suggested action if available
    if suggested_action:
        user_message += f". {suggested_action}"
        
    return user_message
