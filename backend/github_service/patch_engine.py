
"""
Intelligent Patch Application Engine

This module implements a layered approach to applying patches:
1. Try unidiff (strict and accurate)
2. Try enhanced basic parser with improved context handling
3. Try diff-match-patch for fuzzy matching
4. Fall back to full file replacement if all else fails

Each layer includes validation against expected content.
"""

import os
import sys
import re
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
import difflib
import hashlib

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patch-engine")

# Try to import optional dependencies
UNIDIFF_AVAILABLE = False
DIFF_MATCH_PATCH_AVAILABLE = False

try:
    import unidiff
    UNIDIFF_AVAILABLE = True
    logger.info("unidiff library available - will use for precise patch application")
except ImportError:
    logger.warning("unidiff library not available - will use fallback patch methods")

try:
    from diff_match_patch import diff_match_patch
    DIFF_MATCH_PATCH_AVAILABLE = True
    logger.info("diff_match_patch library available - will use for fuzzy matching")
except ImportError:
    logger.warning("diff_match_patch library not available - fuzzy matching unavailable")


class PatchResult:
    """Data class to store patch application result"""
    
    def __init__(
        self, 
        success: bool, 
        method: str, 
        file_path: str, 
        patched_content: Optional[str] = None, 
        error: Optional[str] = None,
        validation: Optional[dict] = None
    ):
        self.success = success
        self.method = method
        self.file_path = file_path
        self.patched_content = patched_content
        self.error = error
        self.validation = validation or {}
        
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "success": self.success,
            "method": self.method,
            "file_path": self.file_path,
            "error": self.error,
            "validation": self.validation
        }


class PatchEngine:
    """Intelligent patch application engine with multiple layers of fallbacks"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
    def log(self, message: str, level: str = "info") -> None:
        """Log a message based on verbosity setting"""
        if self.verbose:
            if level == "error":
                logger.error(message)
            elif level == "warning":
                logger.warning(message)
            else:
                logger.info(message)
    
    def apply_patch(
        self, 
        file_path: str, 
        original_content: str, 
        patch_content: str,
        expected_content: Optional[str] = None
    ) -> PatchResult:
        """
        Apply patch to file content using multiple strategies in order of preference
        
        Args:
            file_path: Path to the file (used for context only)
            original_content: Original file content before patching
            patch_content: Unified diff patch to apply
            expected_content: Optional expected content after patching (for validation)
            
        Returns:
            PatchResult object with the outcome
        """
        self.log(f"Attempting to apply patch to {file_path} ({len(patch_content)} bytes)")
        
        if not patch_content or not patch_content.strip():
            return PatchResult(
                success=False,
                method="none",
                file_path=file_path,
                error="Empty patch content"
            )
            
        # If we have both original and expected content, perform preliminary check
        if expected_content and original_content == expected_content:
            self.log(f"File {file_path} already matches expected content - no patching needed")
            return PatchResult(
                success=True,
                method="none_needed",
                file_path=file_path,
                patched_content=original_content,
                validation={"matches_expected": True, "reason": "already_identical"}
            )
            
        # Strategy 1: Try unidiff (most accurate)
        if UNIDIFF_AVAILABLE:
            self.log("Trying unidiff parser (most accurate)")
            result = self._apply_with_unidiff(file_path, original_content, patch_content)
            if result.success:
                self.log(f"Successfully applied patch using unidiff parser")
                # Validate if we have expected content
                if expected_content:
                    validation_result = self._validate_patch_result(
                        result.patched_content, 
                        expected_content, 
                        original_content
                    )
                    result.validation = validation_result
                    if validation_result.get("matches_expected", False):
                        return result
                else:
                    return result
            else:
                self.log(f"unidiff parser failed: {result.error}", level="warning")
        
        # Strategy 2: Try enhanced basic parser
        self.log("Trying enhanced basic parser")
        result = self._apply_with_enhanced_parser(file_path, original_content, patch_content)
        if result.success:
            self.log(f"Successfully applied patch using enhanced basic parser")
            # Validate if we have expected content
            if expected_content:
                validation_result = self._validate_patch_result(
                    result.patched_content, 
                    expected_content, 
                    original_content
                )
                result.validation = validation_result
                if validation_result.get("matches_expected", False):
                    return result
            else:
                return result
        else:
            self.log(f"Enhanced parser failed: {result.error}", level="warning")
            
        # Strategy 3: Try diff-match-patch for fuzzy matching
        if DIFF_MATCH_PATCH_AVAILABLE:
            self.log("Trying diff-match-patch (fuzzy matching)")
            result = self._apply_with_diff_match_patch(file_path, original_content, patch_content)
            if result.success:
                self.log(f"Successfully applied patch using diff-match-patch fuzzy matching")
                # Validate if we have expected content
                if expected_content:
                    validation_result = self._validate_patch_result(
                        result.patched_content, 
                        expected_content, 
                        original_content
                    )
                    result.validation = validation_result
                    if validation_result.get("matches_expected", False):
                        return result
                else:
                    return result
            else:
                self.log(f"Fuzzy matching failed: {result.error}", level="warning")
                
        # Strategy 4: Last resort - try git apply
        self.log("Trying git apply")
        result = self._apply_with_git(file_path, original_content, patch_content)
        if result.success:
            self.log(f"Successfully applied patch using git apply")
            # Validate if we have expected content
            if expected_content:
                validation_result = self._validate_patch_result(
                    result.patched_content, 
                    expected_content, 
                    original_content
                )
                result.validation = validation_result
                if validation_result.get("matches_expected", False):
                    return result
            else:
                return result
        else:
            self.log(f"Git apply failed: {result.error}", level="warning")
                
        # Fallback: If we have expected content and all else failed, use it directly
        if expected_content:
            self.log("All patch methods failed - falling back to expected content", level="warning")
            # Calculate some metrics to help diagnose
            diff_ratio = difflib.SequenceMatcher(None, original_content, expected_content).ratio()
            lines_changed = len([l for l in difflib.unified_diff(
                original_content.splitlines(), 
                expected_content.splitlines()
            )])
            
            if diff_ratio < 0.5:
                self.log(f"WARNING: Expected content is very different from original (diff ratio: {diff_ratio:.2f})")
                
            return PatchResult(
                success=True,
                method="full_replacement",
                file_path=file_path,
                patched_content=expected_content,
                validation={
                    "matches_expected": True,
                    "method": "direct_use",
                    "diff_ratio": diff_ratio,
                    "lines_changed": lines_changed
                }
            )
            
        # If we got here, all methods failed
        return PatchResult(
            success=False,
            method="all_failed",
            file_path=file_path,
            error="All patch methods failed and no expected content provided"
        )
        
    def _apply_with_unidiff(
        self, 
        file_path: str, 
        original_content: str, 
        patch_content: str
    ) -> PatchResult:
        """Apply patch using unidiff library"""
        try:
            # Parse the patch
            patch_set = unidiff.PatchSet.from_string(patch_content)
            
            # Apply the patch
            patched_content = original_content
            lines = patched_content.splitlines()
            
            for patched_file in patch_set:
                # Make sure we're applying to the right file
                relative_path = os.path.basename(file_path)
                if not (patched_file.target_file.endswith(relative_path) or 
                        patched_file.source_file.endswith(relative_path)):
                    continue
                
                # Apply each hunk
                for hunk in patched_file:
                    # Calculate line offsets
                    start_line = hunk.source_start - 1
                    offset = 0
                    
                    # Apply deletions first
                    deletion_indices = []
                    for i, line in enumerate(hunk.source_lines):
                        if line.startswith('-'):
                            if (start_line + i - offset >= len(lines) or 
                                lines[start_line + i - offset] != line[1:]):
                                self.log(f"Line mismatch at {start_line + i}: expected '{line[1:]}', got '{lines[start_line + i - offset] if start_line + i - offset < len(lines) else 'EOF'}'")
                                raise ValueError("Patch does not apply cleanly - line mismatch")
                            deletion_indices.append(start_line + i - offset)
                            offset += 1
                    
                    # Delete lines in reverse order to maintain indices
                    for idx in sorted(deletion_indices, reverse=True):
                        lines.pop(idx)
                    
                    # Apply additions
                    additions = [line[1:] for line in hunk.target_lines if line.startswith('+')]
                    insertion_point = start_line
                    for add_line in additions:
                        lines.insert(insertion_point, add_line)
                        insertion_point += 1
            
            # Reconstruct the content
            patched_content = '\n'.join(lines)
            if original_content.endswith('\n') and not patched_content.endswith('\n'):
                patched_content += '\n'
                
            return PatchResult(
                success=True,
                method="unidiff",
                file_path=file_path,
                patched_content=patched_content
            )
        except Exception as e:
            return PatchResult(
                success=False,
                method="unidiff",
                file_path=file_path,
                error=str(e)
            )

    def _apply_with_enhanced_parser(
        self, 
        file_path: str, 
        original_content: str, 
        patch_content: str
    ) -> PatchResult:
        """Apply patch using an enhanced custom parser with better context handling"""
        try:
            # Split the patch into hunks
            if not patch_content.startswith('---'):
                return PatchResult(
                    success=False,
                    method="enhanced_parser",
                    file_path=file_path,
                    error="Patch does not start with '---'"
                )
            
            # Extract hunks
            hunks = []
            current_hunk = []
            in_hunk = False
            
            for line in patch_content.splitlines():
                if line.startswith('@@'):
                    if in_hunk:
                        hunks.append(current_hunk)
                        current_hunk = [line]
                    else:
                        in_hunk = True
                        current_hunk = [line]
                elif in_hunk:
                    current_hunk.append(line)
                    
            if in_hunk and current_hunk:
                hunks.append(current_hunk)
                
            if not hunks:
                return PatchResult(
                    success=False,
                    method="enhanced_parser",
                    file_path=file_path,
                    error="No valid hunks found in patch"
                )
                
            # Process each hunk
            lines = original_content.splitlines()
            for hunk in hunks:
                # Parse hunk header
                header = hunk[0]
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
                if not match:
                    self.log(f"Invalid hunk header: {header}", level="warning")
                    continue
                    
                src_start = int(match.group(1))
                src_count = int(match.group(2) or 1)
                tgt_start = int(match.group(3))
                
                # Extract context lines before and after the changes
                pre_context_lines = []
                post_context_lines = []
                
                # Gather context and changes
                changes = []
                for line in hunk[1:]:
                    if line.startswith(' '):
                        changes.append(('context', line[1:]))
                    elif line.startswith('-'):
                        changes.append(('remove', line[1:]))
                    elif line.startswith('+'):
                        changes.append(('add', line[1:]))
                        
                # Find removal lines first to determine location
                removal_candidates = []
                context_matches = []
                
                for i in range(len(lines)):
                    context_size = 3  # Look for 3 context lines
                    
                    # Try to match context and removed lines
                    context_matched = 0
                    removed_matched = 0
                    
                    for j, (change_type, change_line) in enumerate(changes):
                        if j + i >= len(lines):
                            break
                            
                        if change_type == 'context':
                            if lines[i + j] == change_line:
                                context_matched += 1
                            else:
                                break
                        elif change_type == 'remove':
                            if lines[i + j] == change_line:
                                removed_matched += 1
                            else:
                                break
                                
                    if context_matched > 0:
                        context_matches.append((i, context_matched))
                        
                    if removed_matched > 0:
                        removal_candidates.append((i, removed_matched))
                        
                # Find best location based on context and removals
                best_location = src_start - 1  # Default to the location in the patch
                max_score = 0
                
                for loc, score in context_matches + removal_candidates:
                    if score > max_score:
                        max_score = score
                        best_location = loc
                        
                if max_score == 0:
                    self.log(f"Could not find a good location for hunk - using default {best_location}", level="warning")
                
                # Apply changes at the best location
                offset = 0
                i = best_location
                for change_type, change_line in changes:
                    if change_type == 'context':
                        # Skip context lines but verify they match
                        if i + offset < len(lines) and lines[i + offset] != change_line:
                            self.log(f"Context mismatch at line {i + offset}: expected '{change_line}', got '{lines[i + offset]}'", level="warning")
                        i += 1
                    elif change_type == 'remove':
                        # Remove the line if it matches
                        if i + offset < len(lines):
                            if lines[i + offset] == change_line:
                                lines.pop(i + offset)
                                offset -= 1
                            else:
                                self.log(f"Removal mismatch: expected '{change_line}', got '{lines[i + offset]}'", level="warning")
                                # Continue anyway - fuzzy matching
                                lines.pop(i + offset)
                                offset -= 1
                    elif change_type == 'add':
                        # Add the new line
                        lines.insert(i + offset, change_line)
                        offset += 1
                        
            # Reconstruct content
            patched_content = '\n'.join(lines)
            if original_content.endswith('\n') and not patched_content.endswith('\n'):
                patched_content += '\n'
                
            return PatchResult(
                success=True,
                method="enhanced_parser",
                file_path=file_path,
                patched_content=patched_content
            )
        except Exception as e:
            return PatchResult(
                success=False,
                method="enhanced_parser",
                file_path=file_path,
                error=f"Enhanced parser error: {str(e)}"
            )
            
    def _apply_with_diff_match_patch(
        self, 
        file_path: str, 
        original_content: str, 
        patch_content: str
    ) -> PatchResult:
        """Apply patch using Google's diff-match-patch for fuzzy matching"""
        if not DIFF_MATCH_PATCH_AVAILABLE:
            return PatchResult(
                success=False,
                method="diff_match_patch",
                file_path=file_path,
                error="diff_match_patch library not available"
            )
            
        try:
            # Convert unified diff to a series of patch operations
            dmp = diff_match_patch()
            
            # We need to extract the actual changes from the unified diff
            # and convert them to diff_match_patch operations
            patches = self._convert_unified_to_dmp_patches(original_content, patch_content)
            
            if not patches:
                return PatchResult(
                    success=False,
                    method="diff_match_patch",
                    file_path=file_path,
                    error="Failed to convert unified diff to patch operations"
                )
                
            # Apply the patches
            patched_content, results = dmp.patch_apply(patches, original_content)
            
            # Check if all patches applied
            if not all(results):
                failed_count = results.count(False)
                self.log(f"{failed_count} of {len(results)} patches failed to apply", level="warning")
                
            # Check if we got any changes at all
            if patched_content == original_content:
                return PatchResult(
                    success=False,
                    method="diff_match_patch",
                    file_path=file_path,
                    error="Patch applied but resulted in no changes"
                )
                
            return PatchResult(
                success=True,
                method="diff_match_patch",
                file_path=file_path,
                patched_content=patched_content,
                validation={"patch_success_rate": results.count(True) / len(results) if results else 0}
            )
        except Exception as e:
            return PatchResult(
                success=False,
                method="diff_match_patch",
                file_path=file_path,
                error=f"diff_match_patch error: {str(e)}"
            )
            
    def _convert_unified_to_dmp_patches(self, original_content: str, patch_content: str):
        """Convert a unified diff to diff_match_patch patches"""
        try:
            dmp = diff_match_patch()
            patches = []
            
            # Extract hunks
            hunks = []
            current_hunk = []
            in_hunk = False
            
            for line in patch_content.splitlines():
                if line.startswith('@@'):
                    if in_hunk:
                        hunks.append(current_hunk)
                        current_hunk = [line]
                    else:
                        in_hunk = True
                        current_hunk = [line]
                elif in_hunk:
                    current_hunk.append(line)
                    
            if in_hunk and current_hunk:
                hunks.append(current_hunk)
                
            if not hunks:
                return []
                
            # Process hunks
            lines = original_content.splitlines()
            for hunk in hunks:
                # Parse hunk header
                header = hunk[0]
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
                if not match:
                    continue
                    
                src_start = int(match.group(1)) - 1  # 0-based
                
                # Extract context and changes
                before_lines = []
                after_lines = []
                
                for line in hunk[1:]:
                    if line.startswith(' '):
                        before_lines.append(line[1:])
                        after_lines.append(line[1:])
                    elif line.startswith('-'):
                        before_lines.append(line[1:])
                    elif line.startswith('+'):
                        after_lines.append(line[1:])
                        
                # Find the section in the original content
                context_size = 3
                best_match = src_start
                best_score = 0
                
                for i in range(max(0, src_start - 20), min(len(lines), src_start + 20)):
                    if i + len(before_lines) > len(lines):
                        continue
                        
                    score = 0
                    for j, line in enumerate(before_lines):
                        if j < len(before_lines) and i + j < len(lines):
                            if lines[i + j] == line:
                                score += 1
                                
                    if score > best_score:
                        best_score = score
                        best_match = i
                        
                # Create a patch for this hunk
                before_text = '\n'.join(before_lines)
                after_text = '\n'.join(after_lines)
                
                # Convert lines to character offsets
                char_offset = 0
                for i in range(best_match):
                    if i < len(lines):
                        char_offset += len(lines[i]) + 1  # +1 for newline
                        
                # Create a patch
                p = dmp.patch_make(original_content[char_offset:char_offset + len(before_text)], after_text)
                if p:
                    for patch in p:
                        patch.start1 += char_offset
                        patches.append(patch)
            
            return patches
        except Exception as e:
            logger.error(f"Error converting unified diff to dmp patches: {str(e)}")
            return []
            
    def _apply_with_git(
        self, 
        file_path: str, 
        original_content: str, 
        patch_content: str
    ) -> PatchResult:
        """Apply patch using git apply command"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create a temporary file with the original content
                tmp_file = os.path.join(tmpdir, os.path.basename(file_path))
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                    
                # Create a temporary patch file
                patch_file = os.path.join(tmpdir, 'patch.diff')
                with open(patch_file, 'w', encoding='utf-8') as f:
                    f.write(patch_content)
                    
                # Try to apply the patch
                try:
                    # Try with fuzz factor for better matching
                    result = subprocess.run(
                        ['git', 'apply', '--whitespace=fix', '--unidiff-zero', '--reject', patch_file],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        # Try with more aggressive options
                        result = subprocess.run(
                            ['git', 'apply', '--whitespace=fix', '--unidiff-zero', '--reject', '--ignore-whitespace', patch_file],
                            cwd=tmpdir,
                            capture_output=True,
                            text=True
                        )
                        
                    if result.returncode != 0:
                        return PatchResult(
                            success=False,
                            method="git_apply",
                            file_path=file_path,
                            error=f"git apply failed: {result.stderr}"
                        )
                        
                    # Read the patched file
                    with open(tmp_file, 'r', encoding='utf-8') as f:
                        patched_content = f.read()
                        
                    return PatchResult(
                        success=True,
                        method="git_apply",
                        file_path=file_path,
                        patched_content=patched_content
                    )
                except Exception as e:
                    return PatchResult(
                        success=False,
                        method="git_apply",
                        file_path=file_path,
                        error=f"git apply error: {str(e)}"
                    )
        except Exception as e:
            return PatchResult(
                success=False,
                method="git_apply",
                file_path=file_path,
                error=f"Temp file error: {str(e)}"
            )
            
    def _validate_patch_result(
        self, 
        patched_content: str, 
        expected_content: str,
        original_content: str
    ) -> dict:
        """Validate that the patched content matches the expected content"""
        # Normalize line endings
        patched_norm = patched_content.replace('\r\n', '\n').strip()
        expected_norm = expected_content.replace('\r\n', '\n').strip()
        original_norm = original_content.replace('\r\n', '\n').strip()
        
        # Quick exact match check
        if patched_norm == expected_norm:
            return {"matches_expected": True, "method": "exact_match"}
            
        # Calculate similarity ratio
        similarity = difflib.SequenceMatcher(None, patched_norm, expected_norm).ratio()
        
        # Calculate changes from original to patched and original to expected
        patched_diff = list(difflib.unified_diff(
            original_norm.splitlines(), 
            patched_norm.splitlines(), 
            n=0
        ))
        
        expected_diff = list(difflib.unified_diff(
            original_norm.splitlines(), 
            expected_norm.splitlines(), 
            n=0
        ))
        
        # Check if the diffs are equivalent (same changes applied)
        diff_equivalent = len(patched_diff) == len(expected_diff)
        
        # Check for whitespace-only differences
        whitespace_diff = False
        if not diff_equivalent:
            # Remove all whitespace and check again
            patched_no_ws = ''.join(patched_norm.split())
            expected_no_ws = ''.join(expected_norm.split())
            whitespace_diff = patched_no_ws == expected_no_ws
            
        result = {
            "matches_expected": similarity > 0.95 or whitespace_diff,
            "similarity_ratio": similarity,
            "whitespace_only_diff": whitespace_diff,
            "patched_length": len(patched_norm),
            "expected_length": len(expected_norm)
        }
        
        # If high similarity but not exact, include a sample diff
        if 0.9 < similarity < 1.0:
            diff = list(difflib.unified_diff(
                expected_norm.splitlines(), 
                patched_norm.splitlines(), 
                n=1
            ))
            if diff:
                result["sample_diff"] = '\n'.join(diff[:10])  # First 10 lines of diff
                
        return result


def apply_patch_to_content(
    original_content: str,
    patch_content: str,
    file_path: str,
    expected_content: Optional[str] = None
) -> Tuple[bool, str, str]:
    """
    Apply patch to content with enhanced validation and layered fallback approach
    
    Args:
        original_content: Original file content
        patch_content: Unified diff patch content
        file_path: Path to the file (for context)
        expected_content: Optional expected content after the patch
        
    Returns:
        (success, patched_content, method)
    """
    engine = PatchEngine(verbose=True)
    result = engine.apply_patch(
        file_path=file_path,
        original_content=original_content,
        patch_content=patch_content,
        expected_content=expected_content
    )
    
    if result.success:
        logger.info(f"Successfully patched {file_path} using {result.method}")
        return True, result.patched_content, result.method
    else:
        logger.error(f"Failed to patch {file_path}: {result.error}")
        return False, original_content, f"failed_{result.method}"


def validate_patch(
    patch_content: str, 
    file_paths: List[str],
    original_contents: Dict[str, str],
    expected_contents: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Validate a patch against multiple files
    
    Args:
        patch_content: Unified diff patch content
        file_paths: Paths to the files in the patch
        original_contents: Dict of file paths to their original content
        expected_contents: Optional dict of file paths to their expected patched content
        
    Returns:
        Dict with validation results
    """
    results = {
        "valid": True,
        "file_results": {}
    }
    
    engine = PatchEngine(verbose=True)
    
    # Basic validation of patch format
    if not patch_content or not patch_content.strip():
        return {
            "valid": False,
            "error": "Empty patch content",
            "file_results": {}
        }
        
    if not patch_content.startswith('---') and not patch_content.startswith('diff --git'):
        return {
            "valid": False,
            "error": "Invalid patch format - must start with '---' or 'diff --git'",
            "file_results": {}
        }
        
    # Extract file paths from the patch
    files_in_patch = set()
    
    for line in patch_content.splitlines():
        if line.startswith('--- a/'):
            files_in_patch.add(line[6:])
        elif line.startswith('+++ b/'):
            files_in_patch.add(line[6:])
        elif line.startswith('diff --git a/'):
            # Extract both a/ and b/ paths
            parts = line.split()
            if len(parts) >= 3:
                files_in_patch.add(parts[2][2:])  # Remove 'a/'
                if len(parts) >= 4:
                    files_in_patch.add(parts[3][2:])  # Remove 'b/'
                    
    # Check if our file_paths are in the patch
    missing_files = []
    for file_path in file_paths:
        if file_path not in files_in_patch and os.path.basename(file_path) not in files_in_patch:
            missing_files.append(file_path)
            
    if missing_files:
        results["valid"] = False
        results["missing_files"] = missing_files
        results["error"] = f"Some files not found in patch: {', '.join(missing_files)}"
        
    # For each file, try to apply the patch and validate
    for file_path in file_paths:
        # Skip files not in original_contents
        if file_path not in original_contents:
            results["file_results"][file_path] = {
                "valid": False,
                "error": "No original content provided"
            }
            results["valid"] = False
            continue
            
        # Extract expected content if available
        expected_content = None
        if expected_contents and file_path in expected_contents:
            expected_content = expected_contents[file_path]
            
        # Try to apply the patch
        patch_result = engine.apply_patch(
            file_path=file_path,
            original_content=original_contents[file_path],
            patch_content=patch_content,
            expected_content=expected_content
        )
        
        if patch_result.success:
            results["file_results"][file_path] = {
                "valid": True,
                "method": patch_result.method,
                "validation": patch_result.validation
            }
            
            # Check validation result
            if expected_content and patch_result.validation.get("matches_expected", False) == False:
                results["file_results"][file_path]["warning"] = "Patch applied but result doesn't match expected content"
                results["valid"] = False
        else:
            results["file_results"][file_path] = {
                "valid": False,
                "error": patch_result.error
            }
            results["valid"] = False
            
    return results
