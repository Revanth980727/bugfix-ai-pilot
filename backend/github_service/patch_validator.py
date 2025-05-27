
import re
import os
import logging
from typing import List, Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patch-validator")

class PatchValidator:
    """
    Validates LLM-generated patches for common issues:
    - Invalid file paths
    - Malformed diff syntax
    - Placeholder text or TODO comments
    - Non-existent files
    - Syntax errors
    """
    
    def __init__(self):
        """Initialize the patch validator"""
        self.github_client = None
        
        # Common placeholder patterns in file paths
        self.path_placeholder_patterns = [
            r'/path/to/',
            r'example\.com',
            r'placeholder',
            r'/your/',
            r'/absolute/path',
            r'/home/user/',
            r'/usr/local/path',
            r'/tmp/\w+',
        ]
        
        # Common placeholder patterns in code
        self.code_placeholder_patterns = [
            r'# TODO:.*implement',
            r'//.*TODO:',
            r'\/\*.*TODO:.*\*\/',
            r'your_\w+',
            r'YOUR_\w+',
            r'<your_\w+>',
            r'PLACEHOLDER',
            r'INSERT_\w+_HERE',
            r'to be implemented',
            r'will be implemented',
            r'replace with',
            r'Replace with',
        ]
        
        # Invalid file path patterns
        self.invalid_path_patterns = [
            r'^C:\\',  # Windows paths
            r'^\/dev\/',
            r'^\/proc\/',
            r'^\/sys\/',
            r'\.\./',  # parent directory traversal
        ]
    
    def set_github_client(self, github_client: Any) -> None:
        """
        Set the GitHub client for file existence validation
        
        Args:
            github_client: A GitHub service client that implements check_file_exists
        """
        self.github_client = github_client
        
    def validate_patch(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a patch for common issues
        
        Args:
            patch: A dictionary containing file_path and diff
            
        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "rejection_reason": Optional[str],
                "confidence_penalty": Optional[int]
            }
        """
        if not patch or not isinstance(patch, dict):
            return {
                "valid": False,
                "rejection_reason": "Invalid patch format",
                "confidence_penalty": 30
            }
            
        file_path = patch.get("file_path", "")
        diff = patch.get("diff", "")
        
        if not file_path or not isinstance(file_path, str):
            return {
                "valid": False, 
                "rejection_reason": "Missing or invalid file path",
                "confidence_penalty": 25
            }
            
        if not diff or not isinstance(diff, str):
            return {
                "valid": False,
                "rejection_reason": "Missing or invalid diff",
                "confidence_penalty": 25
            }
            
        # Check if file path is valid
        if not self._is_valid_file_path(file_path):
            return {
                "valid": False,
                "rejection_reason": f"Invalid file path: {file_path}",
                "confidence_penalty": 30
            }
            
        # Check if diff has valid syntax
        if not self._is_valid_diff_syntax(diff):
            return {
                "valid": False,
                "rejection_reason": "Invalid diff syntax",
                "confidence_penalty": 35
            }
            
        # Check for placeholders
        placeholders = self._check_for_placeholders(file_path, diff)
        if placeholders:
            placeholder_types = ', '.join(placeholders)
            return {
                "valid": False,
                "rejection_reason": f"Contains placeholders: {placeholder_types}",
                "confidence_penalty": 40
            }
            
        # Check if file exists when modifying rather than creating
        if self.github_client and not diff.startswith("+++"):  # Not a new file
            file_exists = self.github_client.check_file_exists(file_path)
            if not file_exists:
                return {
                    "valid": False,
                    "rejection_reason": f"File does not exist: {file_path}",
                    "confidence_penalty": 35
                }
                
        # All checks passed
        return {
            "valid": True,
            "confidence_boost": 10
        }
            
    def _is_valid_file_path(self, file_path: str) -> bool:
        """
        Check if a file path is valid
        
        Args:
            file_path: Path to validate
            
        Returns:
            Boolean indicating if the path is valid
        """
        # Empty path is invalid
        if not file_path:
            return False
            
        # Check for invalid path patterns
        for pattern in self.invalid_path_patterns:
            if re.search(pattern, file_path):
                logger.info(f"Invalid path pattern found in {file_path}: {pattern}")
                return False
        
        # Basic path validation
        try:
            # Remove leading slash if present
            normalized_path = file_path.lstrip('/')
            
            # Check if path contains invalid characters
            invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
            if any(c in normalized_path for c in invalid_chars):
                logger.info(f"Invalid characters in path: {file_path}")
                return False
                
            # Valid path extensions for code files
            valid_extensions = [
                '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss',
                '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rb',
                '.php', '.sh', '.bat', '.ps1', '.md', '.txt', '.json', '.yml',
                '.yaml', '.toml', '.ini', '.cfg', '.conf', '.xml', '.svg'
            ]
            
            # Check if path has a valid extension
            has_valid_extension = False
            for ext in valid_extensions:
                if file_path.endswith(ext):
                    has_valid_extension = True
                    break
                    
            if not has_valid_extension:
                logger.info(f"Invalid file extension in path: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating path {file_path}: {str(e)}")
            return False
    
    def _is_valid_diff_syntax(self, diff: str) -> bool:
        """
        Check if the diff has valid syntax
        
        Args:
            diff: Diff content to validate
            
        Returns:
            Boolean indicating if the diff syntax is valid
        """
        # Empty diff is invalid
        if not diff:
            return False
            
        try:
            # Check for common diff patterns
            has_diff_header = bool(re.search(r'^(\+\+\+|\-\-\-|@@)', diff, re.MULTILINE))
            
            # If it has proper diff headers, it's likely a valid diff
            if has_diff_header:
                return True
                
            # If it doesn't have diff headers, it might be raw file content
            # In that case, accept it if it's not too short
            if len(diff) > 10:  # Arbitrary threshold to avoid empty/trivial content
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error validating diff syntax: {str(e)}")
            return False
    
    def _check_for_placeholders(self, file_path: str, diff: str) -> List[str]:
        """
        Check for common placeholder patterns in the path and diff
        
        Args:
            file_path: Path to check for placeholders
            diff: Diff content to check for placeholders
            
        Returns:
            List of placeholder types found, empty if none
        """
        found_placeholders = []
        
        # Check path for placeholders
        for pattern in self.path_placeholder_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                found_placeholders.append(f"path_placeholder:{pattern}")
                
        # Check diff for placeholders
        for pattern in self.code_placeholder_patterns:
            if re.search(pattern, diff, re.IGNORECASE):
                found_placeholders.append(f"code_placeholder:{pattern}")
                
        # Check for TODO comments
        if re.search(r'TODO', diff):
            found_placeholders.append("todo_comment")
            
        return found_placeholders
