
import logging
import json
import traceback
from typing import Dict, Any, Optional, List, Tuple, Union

# Configure module logger
logger = logging.getLogger("github-service-logs")

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


def log_operation_attempt(logger: logging.Logger, operation: str, details: Dict[str, Any]) -> None:
    """Log the start of a GitHub operation with details"""
    logger.info(f"GitHub operation started: {operation}")
    logger.info(f"Operation details: {json.dumps(details, default=str)}")


def log_operation_result(logger: logging.Logger, operation: str, success: bool, 
                         details: Optional[Dict[str, Any]] = None) -> None:
    """Log the result of a GitHub operation"""
    if success:
        logger.info(f"GitHub operation succeeded: {operation}")
    else:
        logger.error(f"GitHub operation failed: {operation}")
        
    if details:
        logger.info(f"Result details: {json.dumps(details, default=str)}")


def get_error_metadata(exception: Exception) -> Dict[str, Any]:
    """Extract metadata from an exception"""
    metadata = {
        'errorType': type(exception).__name__,
        'message': str(exception),
        'traceback': traceback.format_exc()
    }
    
    # If it's our custom exception, include its metadata
    if isinstance(exception, GitHubOperationError):
        metadata.update({
            'operation': exception.operation,
            'metadata': exception.metadata,
            'errorCode': exception.error_code
        })
        
        # Include original exception details if available
        if exception.original_exception:
            metadata['originalError'] = {
                'errorType': type(exception.original_exception).__name__,
                'message': str(exception.original_exception)
            }
    
    return metadata


def format_validation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format validation result for consistent display and logging"""
    return {
        'fileList': result.get('fileList', []),
        'totalFiles': result.get('totalFiles', 0),
        'validFiles': len(result.get('fileList', [])),
        'validationDetails': result.get('validationDetails', {
            'totalPatches': 0,
            'validPatches': 0,
            'rejectedPatches': 0,
            'rejectionReasons': {}
        }),
        'changesVerified': result.get('changesVerified', False),
        'fileChecksums': result.get('fileChecksums', {}),
        'fileValidation': result.get('fileValidation', {})
    }


def log_diff_summary(logger: logging.Logger, filename: str, diff_content: str,
                   max_preview_length: int = 500) -> Dict[str, Any]:
    """Log a summary of diff content and return statistics"""
    lines = diff_content.splitlines()
    
    # Calculate basic stats
    lines_added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    lines_removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    changed_hunks = sum(1 for line in lines if line.startswith('@@'))
    
    # Create a preview of the diff
    diff_preview = diff_content[:max_preview_length]
    if len(diff_content) > max_preview_length:
        diff_preview += f"... [{len(diff_content) - max_preview_length} more characters]"
        
    # Log the summary
    logger.info(f"Diff summary for {filename}: {lines_added} lines added, {lines_removed} lines removed, {changed_hunks} hunks")
    logger.info(f"Diff preview for {filename}:\n{diff_preview}")
    
    return {
        'filename': filename,
        'linesAdded': lines_added,
        'linesRemoved': lines_removed,
        'changedHunks': changed_hunks,
        'diffSize': len(diff_content)
    }


def create_structured_error(error_code: str, message: str, file_path: Optional[str] = None, 
                           suggested_action: Optional[str] = None, 
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a structured error object for consistent error reporting
    
    Args:
        error_code: Error code from GitHubError constants
        message: Error message
        file_path: Path to the file that caused the error (if applicable)
        suggested_action: Suggested remedy for the user
        metadata: Additional error metadata
        
    Returns:
        Structured error dictionary
    """
    error = {
        'code': error_code,
        'message': message
    }
    
    if file_path:
        error['file_path'] = file_path
        
    if suggested_action:
        error['suggested_action'] = suggested_action
        
    if metadata:
        error['metadata'] = metadata
        
    return error
