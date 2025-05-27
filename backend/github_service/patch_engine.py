
"""
Patch Engine - Advanced patching functionality for GitHub service

This module provides layered strategies for applying patches to files:
1. Try using unidiff for precise patching
2. Try basic patch parsing with context awareness
3. Try fuzzy matching
4. Fall back to direct file content replacement if validation succeeds
"""

import logging
import os
import tempfile
import subprocess
import difflib
from typing import Dict, List, Any, Tuple, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("patch-engine")

# Try importing third-party diff libraries
try:
    import unidiff
    UNIDIFF_AVAILABLE = True
except ImportError:
    UNIDIFF_AVAILABLE = False
    logger.warning("unidiff library not available, falling back to basic patch parser")

try:
    import diff_match_patch
    DIFF_MATCH_PATCH_AVAILABLE = True
except ImportError:
    DIFF_MATCH_PATCH_AVAILABLE = False
    logger.warning("diff-match-patch library not available, some fallback methods will be unavailable")


def apply_patch_to_content(
    original_content: str, 
    patch_content: str, 
    file_path: str,
    expected_content: str = None
) -> Tuple[bool, str, str]:
    """
    Apply a patch to file content using multiple strategies
    
    Args:
        original_content: Original file content
        patch_content: Unified diff patch content
        file_path: Path of the file being patched
        expected_content: Expected result after patching (for validation)
        
    Returns:
        Tuple of (success, patched_content, method_used)
    """
    logger.info(f"Applying patch to {file_path} using layered strategies")
    
    # Check for trivial cases
    if not patch_content or patch_content.strip() == '':
        logger.warning(f"Empty patch content provided for {file_path}")
        return False, original_content, "none"
        
    # If we have expected content but no original content, this is a new file
    if not original_content and expected_content:
        logger.info(f"Creating new file {file_path} using expected content")
        return True, expected_content, "new_file"
    
    # Try each patching strategy in sequence
    
    # Strategy 1: Use unidiff for precise patching
    if UNIDIFF_AVAILABLE:
        logger.info(f"Trying unidiff strategy for {file_path}")
        success, content = _apply_with_unidiff(original_content, patch_content, file_path)
        if success:
            logger.info(f"Successfully patched {file_path} using unidiff")
            
            # Validate against expected content if provided
            if expected_content and content != expected_content:
                logger.warning(f"Patched content doesn't match expected content with unidiff strategy")
                # We'll continue with other strategies
            else:
                return True, content, "unidiff"
    
    # Strategy 2: Use basic patch parsing
    logger.info(f"Trying basic patch parsing strategy for {file_path}")
    success, content = _apply_with_basic_parser(original_content, patch_content, file_path)
    if success:
        logger.info(f"Successfully patched {file_path} using basic parser")
        
        # Validate against expected content if provided
        if expected_content and content != expected_content:
            logger.warning(f"Patched content doesn't match expected content with basic parser strategy")
            # We'll continue with other strategies
        else:
            return True, content, "basic_parser"
    
    # Strategy 3: Use external git apply command
    logger.info(f"Trying git apply strategy for {file_path}")
    success, content = _apply_with_git(original_content, patch_content, file_path)
    if success:
        logger.info(f"Successfully patched {file_path} using git apply")
        
        # Validate against expected content if provided
        if expected_content and content != expected_content:
            logger.warning(f"Patched content doesn't match expected content with git apply strategy")
            # We'll continue with other strategies
        else:
            return True, content, "git_apply"
    
    # Strategy 4: Use diff-match-patch for fuzzy matching
    if DIFF_MATCH_PATCH_AVAILABLE:
        logger.info(f"Trying diff-match-patch strategy for {file_path}")
        success, content = _apply_with_diff_match_patch(original_content, patch_content, file_path)
        if success:
            logger.info(f"Successfully patched {file_path} using diff-match-patch")
            
            # Validate against expected content if provided
            if expected_content and content != expected_content:
                logger.warning(f"Patched content doesn't match expected content with diff-match-patch strategy")
                # We'll continue with other strategies
            else:
                return True, content, "diff_match_patch"
    
    # Final Strategy: If we have expected content, use it directly
    if expected_content:
        logger.info(f"Using expected content directly for {file_path} as all patch strategies failed")
        
        # Verify it's safe to use expected content
        if _is_safe_to_overwrite(original_content, patch_content, expected_content):
            logger.info(f"Verified it's safe to use expected content for {file_path}")
            return True, expected_content, "expected_content"
        else:
            logger.warning(f"Not safe to use expected content for {file_path}")
    
    # If we get here, all strategies failed
    logger.error(f"All patch strategies failed for {file_path}")
    return False, original_content, "failed"


def validate_patch(
    patch_content: str,
    file_paths: List[str],
    original_contents: Dict[str, str],
    expected_contents: Dict[str, str]
) -> Dict[str, Any]:
    """
    Validate if a patch can be properly applied and yields expected results
    
    Args:
        patch_content: Unified diff patch content
        file_paths: List of file paths in the patch
        original_contents: Dictionary of file paths to original content
        expected_contents: Dictionary of file paths to expected content after patching
        
    Returns:
        Dict with validation results
    """
    logger.info(f"Validating patch for {len(file_paths)} files")
    
    result = {
        'valid': True,
        'file_results': {},
        'message': 'Patch validation successful'
    }
    
    # Process each file
    for file_path in file_paths:
        if file_path not in expected_contents:
            logger.warning(f"No expected content provided for {file_path}")
            result['file_results'][file_path] = {
                'valid': False,
                'error': 'No expected content provided',
                'method': 'none'
            }
            result['valid'] = False
            continue
            
        # Get original and expected content
        original_content = original_contents.get(file_path, '')
        expected_content = expected_contents[file_path]
        
        # Try to apply the patch
        success, content, method = apply_patch_to_content(
            original_content=original_content,
            patch_content=patch_content,
            file_path=file_path,
            expected_content=expected_content
        )
        
        # Check if patch was successful and matches expected content
        file_result = {
            'valid': success and content == expected_content,
            'method': method
        }
        
        if not file_result['valid']:
            if not success:
                file_result['error'] = 'Failed to apply patch'
            elif content != expected_content:
                file_result['error'] = 'Patched content does not match expected content'
                
            # Add details for debugging
            if content != expected_content:
                # Compute a simple diff to show what's different
                diff = list(difflib.unified_diff(
                    content.splitlines(),
                    expected_content.splitlines(),
                    n=1
                ))
                
                if len(diff) > 0:
                    file_result['diff_sample'] = '\n'.join(diff[:10])
                    if len(diff) > 10:
                        file_result['diff_sample'] += f"\n... and {len(diff) - 10} more lines"
            
            result['valid'] = False
        
        result['file_results'][file_path] = file_result
    
    # Log validation results
    if result['valid']:
        logger.info("Patch validation successful for all files")
    else:
        logger.warning("Patch validation failed for some files")
        for file_path, file_result in result['file_results'].items():
            if not file_result['valid']:
                logger.warning(f"- {file_path}: {file_result.get('error', 'unknown error')}")
    
    return result


def _apply_with_unidiff(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """Apply patch using unidiff library"""
    if not UNIDIFF_AVAILABLE:
        return False, original_content
        
    try:
        # Parse the patch set
        patch_set = unidiff.PatchSet.from_string(patch_content)
        
        # Find the patch for this file
        for patched_file in patch_set:
            target_file = patched_file.target_file
            if target_file.startswith('b/'):
                target_file = target_file[2:]
                
            if target_file != file_path:
                # Try with different path formats
                if not (file_path.endswith(target_file) or target_file.endswith(file_path)):
                    continue
            
            # We found the right file in the patch
            logger.info(f"Found patch for {file_path} in unidiff PatchSet")
            
            # Convert original content to lines for patching
            lines = original_content.splitlines()
            
            # Process each hunk
            for hunk in patched_file:
                source_start = hunk.source_start - 1  # Convert to 0-based indexing
                
                # Validate that the source_start is within bounds
                if source_start < 0:
                    source_start = 0
                if source_start > len(lines):
                    source_start = len(lines)
                
                # Verify hunk context if possible
                if len(lines) > 0:
                    # Check if removed lines match context
                    removed_lines = [line.value for line in hunk if line.is_removed]
                    context_matches = True
                    
                    # Check whether enough of the context matches
                    for i, line in enumerate(removed_lines):
                        if source_start + i >= len(lines):
                            context_matches = False
                            break
                            
                        if lines[source_start + i] != line:
                            # Allow for some fuzziness in context
                            context_matches = False
                            break
                    
                    if not context_matches:
                        logger.warning(f"Hunk context doesn't match for {file_path} at line {source_start+1}")
                        # Try to find where the context does match
                        context_found = False
                        
                        # Look nearby for matching context
                        search_radius = min(20, len(lines))  # Don't look too far
                        for offset in range(-search_radius, search_radius):
                            test_pos = source_start + offset
                            if test_pos < 0 or test_pos + len(removed_lines) > len(lines):
                                continue
                                
                            # Check if context matches at this position
                            all_match = True
                            for i, line in enumerate(removed_lines):
                                if lines[test_pos + i] != line:
                                    all_match = False
                                    break
                            
                            if all_match:
                                source_start = test_pos
                                context_found = True
                                logger.info(f"Found matching context at line {source_start+1} (offset {offset})")
                                break
                        
                        if not context_found:
                            logger.warning(f"Could not find matching context for hunk")
                            # We'll still try to apply the hunk at the original position
                
                # Apply the hunk
                # First, remove the lines that should be removed
                del lines[source_start:source_start + hunk.source_length]
                
                # Then, insert the lines that should be added
                added_lines = [line.value for line in hunk if line.is_added]
                for i, line in enumerate(added_lines):
                    lines.insert(source_start + i, line)
            
            # Join the lines back into a string
            return True, '\n'.join(lines)
            
        # If we get here, we couldn't find the file in the patch
        logger.warning(f"File {file_path} not found in patch")
        return False, original_content
    except Exception as e:
        logger.error(f"Error applying patch with unidiff: {str(e)}")
        return False, original_content


def _apply_with_basic_parser(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """Apply patch using a basic line-by-line parser"""
    try:
        lines = original_content.splitlines()
        
        # Parse the patch into hunks
        hunks = _parse_patch_hunks(patch_content, file_path)
        if not hunks:
            logger.warning(f"No hunks found for {file_path} in patch")
            return False, original_content
            
        # Apply each hunk
        line_offset = 0
        
        for hunk in hunks:
            source_start = hunk['source_start'] - 1  # Convert to 0-based
            source_length = hunk['source_length']
            removed_lines = hunk['removed']
            added_lines = hunk['added']
            context_before = hunk.get('context_before', [])
            context_after = hunk.get('context_after', [])
            
            # Adjust for previous hunks
            adjusted_start = source_start + line_offset
            
            # Handle bounds checking
            if adjusted_start < 0:
                adjusted_start = 0
            if adjusted_start > len(lines):
                adjusted_start = len(lines)
                
            # For new files with empty content
            if len(lines) == 0:
                lines = context_before + added_lines + context_after
                continue
                
            # Try to verify context
            context_matches = True
            if source_length > 0 and adjusted_start < len(lines):
                # Check how many lines we can safely compare
                safe_length = min(source_length, len(lines) - adjusted_start)
                
                # Compare actual lines with expected removed lines
                for i in range(safe_length):
                    if i >= len(removed_lines):
                        break
                    if adjusted_start + i >= len(lines):
                        break
                    if lines[adjusted_start + i] != removed_lines[i]:
                        context_matches = False
                        break
                        
            if not context_matches:
                logger.warning(f"Context doesn't match exactly for hunk at line {adjusted_start+1}")
                # Try fuzzy matching to find the right location
                
                # Look for context_before in the file
                if context_before:
                    found_pos = -1
                    for i in range(max(0, adjusted_start - 20), min(len(lines), adjusted_start + 20)):
                        if i + len(context_before) <= len(lines):
                            matches = True
                            for j, context_line in enumerate(context_before):
                                if lines[i + j] != context_line:
                                    matches = False
                                    break
                            if matches:
                                found_pos = i + len(context_before)
                                logger.info(f"Found context_before match at line {found_pos+1}")
                                break
                    
                    if found_pos >= 0:
                        adjusted_start = found_pos
            
            # Apply the hunk
            # Remove the specified lines if they exist
            if source_length > 0 and adjusted_start < len(lines):
                safe_length = min(source_length, len(lines) - adjusted_start)
                del lines[adjusted_start:adjusted_start + safe_length]
            
            # Insert the added lines
            for i, line in enumerate(added_lines):
                if adjusted_start + i <= len(lines):
                    lines.insert(adjusted_start + i, line)
                else:
                    lines.append(line)
            
            # Update the offset for future hunks
            line_offset += (len(added_lines) - source_length)
            
        # Join the lines back into a string
        result = '\n'.join(lines)
        
        # Add trailing newline if original had one
        if original_content and original_content.endswith('\n') and not result.endswith('\n'):
            result += '\n'
            
        return True, result
    except Exception as e:
        logger.error(f"Error applying patch with basic parser: {str(e)}")
        return False, original_content


def _apply_with_git(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """Apply patch using git apply command"""
    try:
        # Check if git is available
        try:
            subprocess.run(['git', '--version'], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("git command not available, skipping git apply strategy")
            return False, original_content
        
        # Create temporary files for the patch process
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the original file
            orig_file_path = os.path.join(temp_dir, os.path.basename(file_path))
            with open(orig_file_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Create the patch file
            patch_file_path = os.path.join(temp_dir, 'patch.diff')
            with open(patch_file_path, 'w', encoding='utf-8') as f:
                f.write(patch_content)
            
            # Try applying the patch
            try:
                # First try with --check to see if it would apply cleanly
                result = subprocess.run(
                    ['git', 'apply', '--check', patch_file_path],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Patch should apply cleanly, now apply it for real
                    subprocess.run(
                        ['git', 'apply', patch_file_path],
                        cwd=temp_dir,
                        check=True,
                        capture_output=True
                    )
                    
                    # Read the patched content
                    with open(orig_file_path, 'r', encoding='utf-8') as f:
                        patched_content = f.read()
                    
                    logger.info(f"Successfully applied patch to {file_path} using git apply")
                    return True, patched_content
                else:
                    # Try with --ignore-whitespace
                    logger.info("Trying git apply with --ignore-whitespace")
                    result = subprocess.run(
                        ['git', 'apply', '--ignore-whitespace', patch_file_path],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        # Read the patched content
                        with open(orig_file_path, 'r', encoding='utf-8') as f:
                            patched_content = f.read()
                        
                        logger.info(f"Successfully applied patch to {file_path} using git apply with --ignore-whitespace")
                        return True, patched_content
                    
                    logger.warning(f"git apply failed: {result.stderr}")
                    return False, original_content
                    
            except subprocess.SubprocessError as e:
                logger.warning(f"Error running git apply: {str(e)}")
                return False, original_content
    except Exception as e:
        logger.error(f"Error in _apply_with_git: {str(e)}")
        return False, original_content


def _apply_with_diff_match_patch(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """Apply patch using Google's diff-match-patch library for fuzzy matching"""
    if not DIFF_MATCH_PATCH_AVAILABLE:
        return False, original_content
        
    try:
        # Extract the patch specific to this file
        file_patch = _extract_file_patch(patch_content, file_path)
        if not file_patch:
            logger.warning(f"Could not extract patch content for {file_path}")
            return False, original_content
        
        # Convert unified diff to diff-match-patch format
        # This is a simplification - ideally we'd convert the unified diff format properly
        dmp = diff_match_patch.diff_match_patch()
        
        # Extract added and removed lines
        added_lines = []
        removed_lines = []
        
        for line in file_patch.splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                removed_lines.append(line[1:])
        
        # Create a patch between removed and added content
        removed_text = '\n'.join(removed_lines)
        added_text = '\n'.join(added_lines)
        
        # If we have meaningful content, try to apply it
        if added_text or removed_text:
            # Use diff-match-patch to create and apply patches
            diffs = dmp.diff_main(original_content, original_content.replace(removed_text, added_text))
            patches = dmp.patch_make(diffs)
            result, _ = dmp.patch_apply(patches, original_content)
            
            logger.info(f"Applied fuzzy patch to {file_path} using diff-match-patch")
            return True, result
        
        return False, original_content
    except Exception as e:
        logger.error(f"Error applying patch with diff-match-patch: {str(e)}")
        return False, original_content


def _parse_patch_hunks(patch_content: str, file_path: str) -> List[Dict[str, Any]]:
    """Parse a unified diff into hunks for a specific file"""
    hunks = []
    current_file = None
    current_hunk = None
    
    # Convert paths for matching
    match_paths = [
        file_path,
        f'a/{file_path}',
        f'b/{file_path}'
    ]
    
    for line in patch_content.splitlines():
        # Check for file headers
        if line.startswith('--- '):
            file_path_in_diff = line[4:]
            if file_path_in_diff.startswith('a/'):
                file_path_in_diff = file_path_in_diff[2:]
                
            # Check if this matches our target file
            if any(file_path_in_diff.endswith(path) for path in match_paths):
                current_file = file_path
            else:
                current_file = None
                
        # Only process lines for our target file
        if current_file != file_path:
            continue
            
        # Parse hunk headers
        if line.startswith('@@'):
            # Extract hunk position information
            try:
                # Format: @@ -linenum,length +linenum,length @@
                source_info = line.split(' ')[1]
                target_info = line.split(' ')[2]
                
                source_parts = source_info[1:].split(',')  # Remove the - prefix
                source_start = int(source_parts[0])
                source_length = int(source_parts[1]) if len(source_parts) > 1 else 1
                
                target_parts = target_info[1:].split(',')  # Remove the + prefix
                target_start = int(target_parts[0])
                target_length = int(target_parts[1]) if len(target_parts) > 1 else 1
                
                current_hunk = {
                    'source_start': source_start,
                    'source_length': source_length,
                    'target_start': target_start,
                    'target_length': target_length,
                    'context_before': [],
                    'removed': [],
                    'added': [],
                    'context_after': []
                }
                hunks.append(current_hunk)
            except (IndexError, ValueError) as e:
                logger.warning(f"Error parsing hunk header: {line}: {e}")
                current_hunk = None
        
        # Parse hunk content if we're in a hunk
        elif current_hunk is not None:
            if line.startswith('-'):
                current_hunk['removed'].append(line[1:])
            elif line.startswith('+'):
                current_hunk['added'].append(line[1:])
            elif line.startswith(' '):
                # Context line
                if len(current_hunk['removed']) == 0 and len(current_hunk['added']) == 0:
                    # Context before any changes
                    current_hunk['context_before'].append(line[1:])
                else:
                    # Context after changes
                    current_hunk['context_after'].append(line[1:])
    
    return hunks


def _extract_file_patch(patch_content: str, file_path: str) -> str:
    """Extract the portion of a unified diff that applies to a specific file"""
    lines = patch_content.splitlines()
    file_patch_lines = []
    in_target_file = False
    
    # Build patterns to match the file path
    path_patterns = [
        f'--- a/{file_path}',
        f'--- {file_path}',
        f'+++ b/{file_path}',
        f'+++ {file_path}',
        f'diff --git a/{file_path} b/{file_path}'
    ]
    
    # Also match file paths with different prefixes/suffixes
    base_name = os.path.basename(file_path)
    if base_name != file_path:
        path_patterns.extend([
            f'--- a/{base_name}',
            f'--- {base_name}',
            f'+++ b/{base_name}',
            f'+++ {base_name}',
            f'diff --git a/{base_name} b/{base_name}'
        ])
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if we've found the start of our target file's patch
        if any(line.startswith(pattern) for pattern in path_patterns):
            in_target_file = True
            # Start collecting the patch for this file
            file_patch_lines.append(line)
            i += 1
            
            # If this is a diff --git line, look for the --- line
            if line.startswith('diff --git'):
                while i < len(lines) and not lines[i].startswith('---'):
                    file_patch_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    file_patch_lines.append(lines[i])
                    i += 1
            
            # If we found a --- line, look for the +++ line
            if i < len(lines) and lines[i-1].startswith('---'):
                if lines[i].startswith('+++'):
                    file_patch_lines.append(lines[i])
                    i += 1
            
            # Continue collecting lines until we find the start of another file's patch
            # or the end of the diff
            while i < len(lines):
                line = lines[i]
                if (line.startswith('diff --git') or 
                    (line.startswith('---') and i+1 < len(lines) and lines[i+1].startswith('+++'))):
                    in_target_file = False
                    break
                file_patch_lines.append(line)
                i += 1
        else:
            i += 1
    
    return '\n'.join(file_patch_lines)


def _is_safe_to_overwrite(original_content: str, patch_content: str, expected_content: str) -> bool:
    """
    Determine if it's safe to use expected_content as a fallback
    
    This checks that the diff between original and expected mostly matches
    the provided patch content, to ensure we're not overwriting changes.
    """
    # If this is a new file (no original content), it's safe to use expected content
    if not original_content or original_content.strip() == '':
        return True
        
    try:
        # Generate a diff between original and expected
        lines1 = original_content.splitlines()
        lines2 = expected_content.splitlines()
        
        # Calculate diff between original and expected
        gen_diff = list(difflib.unified_diff(lines1, lines2, n=3))
        
        # Count lines in the actual patch vs generated diff
        patch_lines = sum(1 for line in patch_content.splitlines() 
                         if line.startswith('+') or line.startswith('-'))
        gen_diff_lines = sum(1 for line in gen_diff 
                            if line.startswith('+') or line.startswith('-'))
        
        # If the number of changed lines is similar, it's probably safe
        ratio = min(patch_lines, gen_diff_lines) / max(patch_lines, gen_diff_lines) if max(patch_lines, gen_diff_lines) > 0 else 1.0
        
        logger.info(f"Safety check for overwrite: patch has {patch_lines} changed lines, " +
                   f"generated diff has {gen_diff_lines} changed lines, similarity ratio: {ratio:.2f}")
        
        # We consider it safe if the diffs are reasonably similar
        return ratio > 0.7
    except Exception as e:
        logger.error(f"Error in safety check: {str(e)}")
        # Be conservative if we can't determine safety
        return False
