
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

def is_fallback_disabled() -> bool:
    """Check if fallback to mock mode is disabled"""
    no_fallback = os.environ.get('NO_FALLBACK_MOCK', 'False').lower()
    return no_fallback in ('true', 'yes', '1', 't')

def parse_patch_content(patch_content: str) -> List[Dict[str, Any]]:
    """
    Parse patch content to extract file paths and their changes.
    
    Args:
        patch_content: A string containing the patch data in unified diff format
        
    Returns:
        A list of dictionaries with file_path and content info
    """
    if not patch_content:
        logger.warning("Empty patch content provided")
        return []
    
    try:
        import unidiff
        from io import StringIO
        
        # Parse the patch using unidiff
        patch_set = unidiff.PatchSet(StringIO(patch_content))
        
        file_changes = []
        for patched_file in patch_set:
            file_path = patched_file.target_file.strip('b/')
            
            # Skip /dev/null or non-existent files
            if file_path == '/dev/null' or not file_path:
                continue
                
            # Count line changes
            added_lines = 0
            removed_lines = 0
            for hunk in patched_file:
                added_lines += len([l for l in hunk if l.is_added])
                removed_lines += len([l for l in hunk if l.is_removed])
            
            file_changes.append({
                "file_path": file_path,
                "line_changes": {
                    "added": added_lines,
                    "removed": removed_lines,
                    "total": added_lines + removed_lines
                },
                "patch": str(patched_file)
            })
            
        logger.info(f"Successfully parsed patch content: {len(file_changes)} files modified")
        return file_changes
    except ImportError:
        logger.error("Failed to import unidiff - falling back to basic patch parsing")
        return parse_patch_basic(patch_content)
    except Exception as e:
        logger.error(f"Error parsing patch content: {str(e)}")
        traceback.print_exc()
        return parse_patch_basic(patch_content)

def parse_patch_basic(patch_content: str) -> List[Dict[str, Any]]:
    """
    Basic parser for patch content when unidiff is not available.
    Handles unified diff format to extract file paths and changes.
    
    Args:
        patch_content: A string containing the patch data in unified diff format
        
    Returns:
        A list of dictionaries with file_path and change info
    """
    if not patch_content:
        return []
        
    file_changes = []
    current_file = None
    current_lines_added = 0
    current_lines_removed = 0
    current_patch = []
    
    lines = patch_content.split('\n')
    
    for line in lines:
        # Detect file header lines (simplified for common formats)
        if line.startswith('--- a/') or line.startswith('diff --git a/'):
            # Save previous file if exists
            if current_file:
                file_changes.append({
                    "file_path": current_file,
                    "line_changes": {
                        "added": current_lines_added,
                        "removed": current_lines_removed,
                        "total": current_lines_added + current_lines_removed
                    },
                    "patch": '\n'.join(current_patch)
                })
                
            # Extract new file name for git diff format
            if line.startswith('diff --git'):
                parts = line.split(' ')
                if len(parts) >= 3:
                    current_file = parts[2].strip().lstrip('b/')
                current_lines_added = 0
                current_lines_removed = 0
                current_patch = [line]
            
        # Extract new file for unified diff format
        elif line.startswith('+++ b/'):
            current_file = line.split(' ', 1)[1].strip().lstrip('b/')
            current_patch.append(line)
            
        # Handle diff content lines
        elif current_file is not None:
            current_patch.append(line)
            
            # Count changed lines
            if line.startswith('+') and not line.startswith('+++'):
                current_lines_added += 1
            elif line.startswith('-') and not line.startswith('---'):
                current_lines_removed += 1
    
    # Add the last file if exists
    if current_file:
        file_changes.append({
            "file_path": current_file,
            "line_changes": {
                "added": current_lines_added,
                "removed": current_lines_removed,
                "total": current_lines_added + current_lines_removed
            },
            "patch": '\n'.join(current_patch)
        })
    
    logger.info(f"Basic patch parsing found {len(file_changes)} files modified")
    return file_changes
