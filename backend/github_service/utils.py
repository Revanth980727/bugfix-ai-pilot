
import os
import sys
import logging
from typing import Dict, Any, List, Optional, Callable

# Configure logging
logger = logging.getLogger("github-service-utils")

def is_test_mode() -> bool:
    """Check if running in test mode"""
    # Check for TEST_MODE in environment
    test_mode_var = os.environ.get('TEST_MODE', 'False').lower()
    return test_mode_var in ('true', 'yes', '1', 't')

def is_production() -> bool:
    """Check if running in production mode"""
    # Check for ENVIRONMENT in environment
    env = os.environ.get('ENVIRONMENT', 'development').lower()
    return env == 'production' or env == 'prod'

def prepare_response_metadata(file_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Prepare metadata for API responses"""
    # Extract file validation information
    file_validations = []
    file_checksums = {}
    
    for result in file_results:
        file_path = result.get("file_path", "unknown")
        success = result.get("success", False)
        
        file_validations.append({
            "path": file_path,
            "valid": success,
            "error": result.get("error") if not success else None
        })
        
        # Track checksums for verified files
        if success and "checksum" in result:
            file_checksums[file_path] = result["checksum"]
    
    # Create metadata object
    metadata = {
        "fileValidation": file_validations,
        "fileChecksums": file_checksums,
        "timestamp": os.environ.get('REQUEST_TIME', ''),
        "testMode": is_test_mode()
    }
    
    return metadata

def verify_module_imports() -> bool:
    """Verify that all required modules are imported correctly"""
    required_modules = {
        'github': 'PyGithub',
        'unidiff': 'unidiff',
    }
    
    all_modules_available = True
    
    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
            logger.debug(f"Successfully imported {module_name}")
        except ImportError:
            logger.error(f"Failed to import {module_name} - please install {package_name}")
            all_modules_available = False
    
    return all_modules_available

def safe_import(module_name: str, fail_message: str = None) -> Optional[Any]:
    """Safely import a module, returning None if it fails"""
    try:
        return __import__(module_name)
    except ImportError:
        if fail_message:
            logger.warning(fail_message)
        return None
