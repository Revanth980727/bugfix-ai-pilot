
import os
import logging
import hashlib
import traceback
from typing import Dict, Optional, Any, Tuple, List

# Configure logger
logger = logging.getLogger("github-utils")

class GitHubError:
    """Structured error object for GitHub operations"""
    
    # Error codes for different failure scenarios
    ERR_PATCH_FAILED = "PATCH_FAILED"
    ERR_COMMIT_EMPTY = "COMMIT_EMPTY"
    ERR_VALIDATION_FAILED = "VALIDATION_FAILED"
    ERR_FILE_NOT_FOUND = "FILE_NOT_FOUND"
    ERR_TEST_MODE = "TEST_MODE_REQUIRED"
    ERR_PERMISSION_DENIED = "PERMISSION_DENIED"
    ERR_NO_CHANGES = "NO_CHANGES"
    ERR_IMPORT_FAILED = "IMPORT_FAILED"
    ERR_CONFIG_INVALID = "CONFIG_INVALID"
    
    def __init__(self, code: str, message: str, file_path: Optional[str] = None, 
                 suggested_action: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.file_path = file_path
        self.suggested_action = suggested_action
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses"""
        result = {
            'code': self.code,
            'message': self.message
        }
        
        if self.file_path:
            result['file_path'] = self.file_path
        
        if self.suggested_action:
            result['suggested_action'] = self.suggested_action
            
        if self.metadata:
            result['metadata'] = self.metadata
            
        return result
    
    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        
        if self.file_path:
            parts.append(f"File: {self.file_path}")
            
        if self.suggested_action:
            parts.append(f"Suggestion: {self.suggested_action}")
            
        return " - ".join(parts)


def is_test_mode() -> bool:
    """Centralized function to check if system is running in test mode"""
    # Import directly here to avoid circular imports - fixed path to work within container
    try:
        from github_service.config import TEST_MODE
        return TEST_MODE
    except ImportError:
        # Fall back to local import if module structure is different
        try:
            from config import TEST_MODE
            return TEST_MODE
        except ImportError:
            # Last resort - check environment variable directly
            logger.warning("Could not import TEST_MODE from config, checking env var directly")
            import os
            return os.environ.get('TEST_MODE', 'False').lower() in ('true', 'yes', '1', 't')


def is_production() -> bool:
    """Check if system is running in production environment"""
    return os.environ.get("ENVIRONMENT", "development") == "production"


def should_allow_test_files() -> bool:
    """Determine if test files should be allowed based on environment and test mode"""
    # In production, only allow test files if test mode is explicitly enabled
    if is_production():
        return is_test_mode()
    
    # In non-production environments, allow test files by default
    return True


def calculate_file_checksum(content: str) -> str:
    """Calculate MD5 checksum for a file content string"""
    if not isinstance(content, str):
        # Try to convert content to string if possible
        try:
            if isinstance(content, dict):
                import json
                content = json.dumps(content, sort_keys=True)
            else:
                content = str(content)
        except Exception as e:
            logger.error(f"Failed to convert content for checksum: {e}")
            return "invalid-content"
            
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def is_test_file(file_path: str) -> bool:
    """Check if a file path is a test file"""
    return file_path.endswith('test.md') or '/test/' in file_path


def validate_file_changes(before_content: str, after_content: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate file changes by comparing before and after content
    
    Args:
        before_content: Original file content
        after_content: Modified file content
        
    Returns:
        Tuple of (is_valid, validation_metadata)
    """
    # Calculate checksums
    before_checksum = calculate_file_checksum(before_content)
    after_checksum = calculate_file_checksum(after_content)
    
    # Check if content actually changed
    content_changed = before_checksum != after_checksum
    
    # Check if new content is valid (not empty if original wasn't empty)
    new_content_valid = True
    if before_content and not after_content.strip():
        new_content_valid = False

    # Compare content for more detailed difference analysis
    has_meaningful_changes = False
    if content_changed:
        # Count line changes
        before_lines = before_content.splitlines()
        after_lines = after_content.splitlines()
        lines_added = len(after_lines) - len(before_lines)
        
        # Check for whitespace-only changes
        before_normalized = '\n'.join(line.strip() for line in before_lines if line.strip())
        after_normalized = '\n'.join(line.strip() for line in after_lines if line.strip())
        has_meaningful_changes = before_normalized != after_normalized
    
    # Create validation metadata
    validation_metadata = {
        "beforeChecksum": before_checksum,
        "afterChecksum": after_checksum,
        "contentChanged": content_changed,
        "contentValid": new_content_valid,
        "hasMeaningfulChanges": has_meaningful_changes,
        "beforeLines": len(before_content.splitlines()),
        "afterLines": len(after_content.splitlines()),
        "lineChange": len(after_content.splitlines()) - len(before_content.splitlines())
    }
    
    # Changes are valid if content changed meaningfully and is valid
    is_valid = content_changed and new_content_valid and has_meaningful_changes
    
    return is_valid, validation_metadata


def prepare_response_metadata(file_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Prepare standardized metadata for API responses
    
    Args:
        file_results: List of file operation results
        
    Returns:
        Structured metadata dictionary
    """
    valid_files = [result for result in file_results if result.get("success", False)]
    
    # Check if any files had meaningful changes
    files_with_changes = [result for result in valid_files if 
                         result.get("validation", {}).get("hasMeaningfulChanges", False)]
    
    metadata = {
        "fileList": [result.get("file_path") for result in valid_files],
        "totalFiles": len(file_results),
        "validFiles": len(valid_files),
        "filesWithChanges": len(files_with_changes),
        "fileChecksums": {},
        "fileValidation": {},
        "validationDetails": {
            "totalPatches": len(file_results),
            "validPatches": len(valid_files),
            "rejectedPatches": len(file_results) - len(valid_files),
            "rejectionReasons": {}
        }
    }
    
    # Extract checksums and validation details
    for result in file_results:
        file_path = result.get("file_path")
        if file_path:
            if "checksum" in result:
                metadata["fileChecksums"][file_path] = result["checksum"]
            
            if "validation" in result:
                metadata["fileValidation"][file_path] = result["validation"]
                
            # Track rejection reasons
            if not result.get("success", False) and "error" in result:
                error = result["error"]
                reason = error.get("code", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
                if reason not in metadata["validationDetails"]["rejectionReasons"]:
                    metadata["validationDetails"]["rejectionReasons"][reason] = 0
                metadata["validationDetails"]["rejectionReasons"][reason] += 1
    
    return metadata

def has_meaningful_changes(file_results: List[Dict[str, Any]]) -> bool:
    """
    Check if any files have meaningful changes based on validation results
    
    Args:
        file_results: List of file operation results
        
    Returns:
        True if at least one file has meaningful changes, False otherwise
    """
    for result in file_results:
        if result.get("success", False):
            validation = result.get("validation", {})
            if validation.get("hasMeaningfulChanges", False):
                return True
    return False

def verify_module_imports() -> bool:
    """
    Verify that all required modules can be imported.
    This helps identify import issues early rather than falling back to mocks silently.
    
    Returns:
        True if all required modules can be imported, False otherwise
    """
    required_modules = [
        ('github', 'PyGithub'),
        ('jira', 'jira'),
        ('unidiff', 'unidiff')
    ]
    
    missing_modules = []
    
    for module_name, package_name in required_modules:
        try:
            __import__(module_name)
            logger.info(f"✅ Successfully imported {module_name}")
        except ImportError:
            missing_modules.append((module_name, package_name))
            logger.error(f"❌ Failed to import {module_name} (from package {package_name})")
    
    if missing_modules:
        modules_str = ", ".join([f"{m[0]} (pip install {m[1]})" for m in missing_modules])
        logger.error(f"Missing required modules: {modules_str}")
        logger.error("Please install the missing packages or check your PYTHONPATH")
        return False
    
    return True

def log_exception_with_traceback(e: Exception, context: str = ""):
    """Log an exception with full traceback for better debugging"""
    logger.error(f"Exception in {context or 'operation'}: {str(e)}")
    logger.error(traceback.format_exc())
