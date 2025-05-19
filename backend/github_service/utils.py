
import os
import sys
import logging
import traceback
from typing import Dict, Any, List, Optional, Callable

# Configure logging
logger = logging.getLogger("github-service-utils")

def is_test_mode() -> bool:
    """Check if running in test mode"""
    # Check for TEST_MODE in environment
    test_mode_var = os.environ.get('TEST_MODE', 'False').lower()
    test_mode = test_mode_var in ('true', 'yes', '1', 't')
    
    # Log test mode status
    if test_mode:
        logger.warning("TEST_MODE is enabled - using mock implementations")
        
    return test_mode

def is_production() -> bool:
    """Check if running in production mode"""
    # Check for ENVIRONMENT in environment
    env = os.environ.get('ENVIRONMENT', 'development').lower()
    is_prod = env == 'production' or env == 'prod'
    
    # Log production status
    if is_prod:
        logger.info("Running in PRODUCTION mode")
        
    return is_prod

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
    missing_modules = []
    
    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
            logger.debug(f"Successfully imported {module_name}")
        except ImportError:
            logger.error(f"Failed to import {module_name} - please install {package_name}")
            missing_modules.append(f"{module_name} ({package_name})")
            all_modules_available = False
    
    if missing_modules:
        logger.error(f"Missing required modules: {', '.join(missing_modules)}")
        logger.error("Some functionality may be limited or unavailable")
        
    return all_modules_available

def safe_import(module_name: str, fail_message: str = None) -> Optional[Any]:
    """Safely import a module, returning None if it fails"""
    try:
        module = __import__(module_name)
        logger.debug(f"Successfully imported {module_name}")
        return module
    except ImportError:
        if fail_message:
            logger.warning(fail_message)
        else:
            logger.warning(f"Failed to import {module_name}")
        return None

def ensure_required_modules():
    """Ensure all required modules are available, installing if possible"""
    try:
        # Check for PyGithub
        try:
            import github
            logger.info("PyGithub is installed")
        except ImportError:
            logger.warning("PyGithub not found, attempting to install")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub"])
            logger.info("PyGithub has been installed")
        
        # Check for unidiff
        try:
            import unidiff
            logger.info("unidiff is installed")
        except ImportError:
            logger.warning("unidiff not found, attempting to install")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "unidiff"])
            logger.info("unidiff has been installed")
            
        return True
    except Exception as e:
        logger.error(f"Error ensuring required modules: {str(e)}")
        traceback.print_exc()
        return False
