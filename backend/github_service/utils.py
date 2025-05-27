
"""
Utilities for the GitHub service
"""

import os
import re
import sys
import logging
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib
import functools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-service-utils")

# Optional imports
try:
    import unidiff
    UNIDIFF_AVAILABLE = True
except ImportError:
    UNIDIFF_AVAILABLE = False
    logger.warning("unidiff library not available, falling back to basic patch parser")

# Import our enhanced patch engine
from github_service.patch_engine import apply_patch_to_content, validate_patch


def parse_patch_content(patch_content: str) -> List[Dict[str, Any]]:
    """
    Parse unified diff patch content to extract file paths and changes
    
    Args:
        patch_content: Unified diff patch content
        
    Returns:
        List of dicts with file path and changes
    """
    if not patch_content or not patch_content.strip():
        return []
    
    # Try using unidiff if available for more accurate parsing
    if UNIDIFF_AVAILABLE:
        try:
            return parse_with_unidiff(patch_content)
        except Exception as e:
            logger.warning(f"unidiff parser failed: {str(e)}")
            logger.warning("Falling back to basic patch parser")
    
    # Fall back to basic parser if unidiff fails or isn't available
    return parse_patch_basic(patch_content)


def parse_with_unidiff(patch_content: str) -> List[Dict[str, Any]]:
    """
    Parse patch content using unidiff library
    
    Args:
        patch_content: Unified diff patch content
        
    Returns:
        List of parsed changes
    """
    patch_set = unidiff.PatchSet.from_string(patch_content)
    
    results = []
    for patched_file in patch_set:
        # Extract file path, removing a/ or b/ prefix if present
        source_file = patched_file.source_file
        if source_file.startswith('a/'):
            source_file = source_file[2:]
        elif source_file.startswith('b/'):
            source_file = source_file[2:]
            
        # Count line changes
        added = 0
        removed = 0
        
        for hunk in patched_file:
            added += hunk.added
            removed += hunk.removed
            
        results.append({
            'file_path': source_file,
            'line_changes': {
                'added': added,
                'removed': removed
            },
            'parsed_by': 'unidiff'
        })
        
    return results


def parse_patch_basic(patch_content: str) -> List[Dict[str, Any]]:
    """
    Basic parser for patch content when unidiff is not available
    
    Args:
        patch_content: Unified diff patch content
        
    Returns:
        List of parsed changes
    """
    results = []
    current_file = None
    added_lines = 0
    removed_lines = 0
    
    # Enhanced regex patterns for file headers
    file_header_patterns = [
        r'^--- a/(.*?)$',  # --- a/file.txt
        r'^--- (.*?)$',    # --- file.txt
        r'^diff --git a/(.*?) b/.*?$',  # diff --git a/file.txt b/file.txt
    ]
    
    for line in patch_content.splitlines():
        # Check for file headers using different patterns
        file_match = None
        for pattern in file_header_patterns:
            match = re.match(pattern, line)
            if match:
                file_match = match
                break
                
        if file_match:
            # If we were processing a file, save its results
            if current_file:
                results.append({
                    'file_path': current_file,
                    'line_changes': {
                        'added': added_lines,
                        'removed': removed_lines
                    },
                    'parsed_by': 'basic'
                })
                
            # Start tracking a new file
            current_file = file_match.group(1)
            added_lines = 0
            removed_lines = 0
        elif line.startswith('+') and not line.startswith('+++'):
            # Added line
            added_lines += 1
        elif line.startswith('-') and not line.startswith('---'):
            # Removed line
            removed_lines += 1
            
    # Add the last file if we were processing one
    if current_file:
        results.append({
            'file_path': current_file,
            'line_changes': {
                'added': added_lines,
                'removed': removed_lines
            },
            'parsed_by': 'basic'
        })
        
    return results


def prepare_response_metadata(file_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Prepare metadata for API responses
    
    Args:
        file_results: List of file operation results
        
    Returns:
        Dict with metadata
    """
    valid_files = [r for r in file_results if r.get('success', False)]
    failed_files = [r for r in file_results if not r.get('success', False)]
    
    file_checksums = {}
    for result in valid_files:
        if 'checksum' in result:
            file_checksums[result['file_path']] = result['checksum']
            
    return {
        'timestamp': datetime.now().isoformat(),
        'filesProcessed': len(file_results),
        'filesSucceeded': len(valid_files),
        'filesFailed': len(failed_files),
        'fileChecksums': file_checksums
    }


def is_test_mode() -> bool:
    """Check if running in test mode"""
    return os.environ.get('TEST_MODE', 'false').lower() in ('true', '1', 't')


def is_production() -> bool:
    """Check if running in production mode"""
    env = os.environ.get('ENVIRONMENT', '').lower()
    return env in ('production', 'prod')


def verify_module_imports() -> bool:
    """Verify that required modules can be imported"""
    try:
        # Check for required modules
        import requests
        import json
        
        return True
    except ImportError as e:
        logger.error(f"Failed to import required module: {str(e)}")
        return False


def calculate_checksum(content: str) -> str:
    """Calculate a checksum for file content"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


@functools.lru_cache(maxsize=32)
def detect_file_format(file_path: str) -> str:
    """Detect file format based on extension"""
    ext = os.path.splitext(file_path)[1].lower()
    
    code_extensions = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown',
        '.json': 'json',
        '.yml': 'yaml',
        '.yaml': 'yaml'
    }
    
    return code_extensions.get(ext, 'text')
