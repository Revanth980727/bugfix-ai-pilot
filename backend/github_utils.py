
import logging
import os
import base64
import difflib
import re
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from github import Github, GithubException, InputGitTreeElement

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-utils")

def authenticate_github():
    """Authenticate with GitHub using the personal access token"""
    # Get the GitHub token from environment variables first
    github_token = os.environ.get("GITHUB_TOKEN")
    
    # If not found in environment, try importing from env.py if it exists
    if not github_token:
        try:
            from env import GITHUB_TOKEN
            github_token = GITHUB_TOKEN
        except ImportError:
            logger.error("GitHub token not found. Please set GITHUB_TOKEN environment variable.")
            return None
        
    if not github_token:
        logger.error("GitHub token not found. Please set GITHUB_TOKEN environment variable.")
        return None
        
    try:
        github_client = Github(github_token)
        # Test the connection
        user = github_client.get_user()
        logger.info(f"Authenticated as GitHub user: {user.login}")
        return github_client
    except GithubException as e:
        logger.error(f"GitHub authentication error: {str(e)}")
        return None

def get_repo(repo_name: str = None):
    """Get a repository by name or from environment variables"""
    github_client = authenticate_github()
    if not github_client:
        return None
    
    # If repo_name is provided, use it directly
    if repo_name:
        try:
            return github_client.get_repo(repo_name)
        except GithubException as e:
            logger.error(f"Error accessing repository {repo_name}: {str(e)}")
            return None
    
    # Otherwise try to construct from environment variables
    owner = os.environ.get("GITHUB_REPO_OWNER")
    name = os.environ.get("GITHUB_REPO_NAME")
    
    if not owner or not name:
        logger.error("GITHUB_REPO_OWNER and GITHUB_REPO_NAME environment variables are required")
        return None
    
    try:
        full_name = f"{owner}/{name}"
        return github_client.get_repo(full_name)
    except GithubException as e:
        logger.error(f"Error accessing repository {full_name}: {str(e)}")
        return None

# ... keep existing code (create_branch, commit_changes, create_pull_request functions)

def commit_multiple_changes_as_tree(repo_name: str, branch_name: str, 
                                  file_changes: List[Dict[str, Any]], commit_message: str) -> bool:
    """
    Commit multiple file changes at once using Git trees for better performance
    and atomic commits across multiple files.
    """
    try:
        github_client = authenticate_github()
        if not github_client:
            return False
            
        # Get the repository
        repo = get_repo(repo_name)
        if not repo:
            return False
        
        try:
            # Get the latest commit on the branch
            ref = repo.get_git_ref(f"heads/{branch_name}")
            latest_commit = repo.get_git_commit(ref.object.sha)
            base_tree = latest_commit.tree
            
            # Create tree elements for new files
            tree_elements = []
            for file_change in file_changes:
                filename = file_change.get('filename')
                content = file_change.get('content')
                
                if not filename or content is None:
                    logger.warning(f"Skipping invalid file change: {file_change}")
                    continue
                    
                # Convert content to string if it's not already
                if not isinstance(content, str):
                    content = str(content)
                
                element = InputGitTreeElement(
                    path=filename,
                    mode='100644',  # Regular file mode
                    type='blob',
                    content=content
                )
                tree_elements.append(element)
            
            # Create a tree with the new files
            new_tree = repo.create_git_tree(tree_elements, base_tree)
            
            # Create a commit with the new tree
            new_commit = repo.create_git_commit(
                message=commit_message,
                tree=new_tree,
                parents=[latest_commit]
            )
            
            # Update the reference to point to the new commit
            ref.edit(new_commit.sha)
            
            logger.info(f"Committed {len(tree_elements)} files to {branch_name}")
            return True
        except GithubException as e:
            logger.error(f"Failed to commit files as tree: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error in commit_multiple_changes_as_tree: {str(e)}")
        return False

# ... keep existing code (push_branch, get_branch_commit_history functions)

def get_file_content(repo_name: str, file_path: str, branch: str = None) -> Optional[str]:
    """Get the content of a file from GitHub"""
    try:
        repo = get_repo(repo_name)
        if not repo:
            return None
            
        if not branch:
            branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main")
            
        try:
            file_content = repo.get_contents(file_path, ref=branch)
            if file_content.encoding == "base64":
                return base64.b64decode(file_content.content).decode('utf-8')
            else:
                return file_content.decoded_content.decode('utf-8')
        except GithubException as e:
            logger.error(f"Failed to get file content for {file_path}: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Error getting file content: {str(e)}")
        return None

def generate_diff(original_content: str, modified_content: str, file_path: str) -> str:
    """Generate unified diff between two versions of a file"""
    try:
        # Create a unified diff
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3  # Context lines
        )
        
        return "".join(diff)
    except Exception as e:
        logger.error(f"Error generating diff: {str(e)}")
        return ""

def apply_patch_to_content(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str, str]:
    """
    Apply a patch to file content using multiple strategies
    
    Args:
        original_content: Original file content as string
        patch_content: Unified diff patch content
        file_path: Path of the file being patched (for logging only)
        
    Returns:
        Tuple of (success, result_content, method_used)
    """
    # Extract the specific patch section for this file if patch_content contains multiple files
    file_patch = extract_file_patch(patch_content, file_path)
    
    if not file_patch:
        logger.warning(f"No patch content found for {file_path}")
        return False, original_content, "no_patch_content"
    
    # Strategy 1: Try using git apply (most accurate)
    success, result = try_git_apply(original_content, file_patch, file_path)
    if success:
        return True, result, "git_apply"
    
    # Strategy 2: Try using enhanced basic parser with context
    success, result = try_enhanced_patch_parser(original_content, file_patch, file_path)
    if success:
        return True, result, "enhanced_parser"
    
    # Strategy 3: Try using fuzzy matching algorithm
    success, result = try_fuzzy_patch(original_content, file_patch, file_path)
    if success:
        return True, result, "fuzzy_match"
    
    # If all strategies failed
    logger.error(f"All patch strategies failed for {file_path}")
    return False, original_content, "all_failed"

def extract_file_patch(patch_content: str, file_path: str) -> str:
    """
    Extract patch content for a specific file from a multi-file patch
    """
    file_patch = ""
    in_target_file = False
    next_file_marker = re.compile(r'^--- a/[^\n]+$', re.MULTILINE)
    
    lines = patch_content.splitlines(True)  # keep line endings
    
    for i, line in enumerate(lines):
        # Look for the start of our target file's patch
        if line.startswith(f"--- a/{file_path}") or line.startswith(f"--- {file_path}"):
            in_target_file = True
            file_patch += line
            
            # Add the +++ line that should follow
            if i+1 < len(lines) and (lines[i+1].startswith(f"+++ b/{file_path}") or lines[i+1].startswith(f"+++ {file_path}")):
                file_patch += lines[i+1]
                
        # If we're in the target file's patch, keep adding lines until we hit the next file
        elif in_target_file:
            # Check if this is the start of the next file's patch
            if next_file_marker.match(line) and not line.startswith(f"--- a/{file_path}") and not line.startswith(f"--- {file_path}"):
                break
            file_patch += line
            
    return file_patch

def try_git_apply(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """
    Try to apply patch using git apply command
    """
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.original') as original_file, \
             tempfile.NamedTemporaryFile(mode='w', suffix='.patch') as patch_file:
            
            # Write the original content and patch to temp files
            original_file.write(original_content)
            original_file.flush()
            
            patch_file.write(patch_content)
            patch_file.flush()
            
            # Try to apply the patch
            result = subprocess.run(
                ['git', 'apply', '--check', patch_file.name],
                cwd=os.path.dirname(original_file.name),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.warning(f"git apply --check failed: {result.stderr}")
                return False, original_content
                
            # If check passes, apply the patch
            with open(original_file.name, 'r') as f:
                original_content_before = f.read()
                
            result = subprocess.run(
                ['git', 'apply', patch_file.name],
                cwd=os.path.dirname(original_file.name),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.warning(f"git apply failed: {result.stderr}")
                return False, original_content
                
            # Read the patched content
            with open(original_file.name, 'r') as f:
                patched_content = f.read()
                
            logger.info(f"Successfully applied patch to {file_path} using git apply")
            return True, patched_content
            
    except Exception as e:
        logger.error(f"Error during git apply: {str(e)}")
        return False, original_content

def try_enhanced_patch_parser(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """
    Try to apply patch using an enhanced version of the basic patch parser
    with better context matching
    """
    try:
        # Parse the patch into hunks
        hunks = parse_patch_hunks(patch_content)
        if not hunks:
            logger.warning(f"No valid hunks found in patch for {file_path}")
            return False, original_content
            
        # Apply each hunk to the content
        result_content = original_content
        for hunk in hunks:
            result_content = apply_hunk_with_context(result_content, hunk)
            
        # Check if content actually changed
        if result_content == original_content:
            logger.warning(f"Enhanced parser did not modify content for {file_path}")
            return False, original_content
            
        logger.info(f"Successfully applied patch to {file_path} using enhanced parser")
        return True, result_content
        
    except Exception as e:
        logger.error(f"Error during enhanced patch parsing: {str(e)}")
        return False, original_content
        
def parse_patch_hunks(patch_content: str) -> List[Dict[str, Any]]:
    """
    Parse a unified diff patch into structured hunks
    """
    hunks = []
    current_hunk = None
    
    # Regular expression to match hunk header
    hunk_header_pattern = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$')
    
    for line in patch_content.splitlines():
        # Skip file headers
        if line.startswith('---') or line.startswith('+++'):
            continue
            
        # Parse hunk header
        match = hunk_header_pattern.match(line)
        if match:
            # Start a new hunk
            start_line = int(match.group(1))
            line_count = int(match.group(2) or 1)
            new_start = int(match.group(3))
            new_count = int(match.group(4) or 1)
            hunk_desc = match.group(5).strip() if match.group(5) else ""
            
            current_hunk = {
                'start_line': start_line,
                'line_count': line_count,
                'new_start': new_start,
                'new_count': new_count,
                'description': hunk_desc,
                'context_before': [],
                'context_after': [],
                'lines_removed': [],
                'lines_added': []
            }
            hunks.append(current_hunk)
            
        elif current_hunk is not None:
            # Add lines to the current hunk
            if line.startswith(' '):
                # Context line
                if not current_hunk['lines_removed'] and not current_hunk['lines_added']:
                    # Context before changes
                    current_hunk['context_before'].append(line[1:])
                else:
                    # Context after changes
                    current_hunk['context_after'].append(line[1:])
                    
            elif line.startswith('-'):
                # Line removed
                current_hunk['lines_removed'].append(line[1:])
                
            elif line.startswith('+'):
                # Line added
                current_hunk['lines_added'].append(line[1:])
    
    return hunks

def apply_hunk_with_context(content: str, hunk: Dict[str, Any]) -> str:
    """
    Apply a parsed hunk to content with context matching
    """
    lines = content.splitlines()
    result_lines = []
    
    # Try to find the correct location for the hunk
    context_before = hunk['context_before']
    context_after = hunk['context_after']
    lines_removed = hunk['lines_removed']
    lines_added = hunk['lines_added']
    target_line = hunk['start_line'] - 1  # 0-indexed
    
    # If we have context before, try to find exact match for better positioning
    best_position = None
    max_context_matched = -1
    
    # Try to find the best position based on context matching
    for i in range(len(lines)):
        # Skip if we don't have enough lines left
        if i + len(context_before) + len(lines_removed) > len(lines):
            continue
            
        # Check if context before matches at this position
        context_matches = sum(1 for j, ctx_line in enumerate(context_before) 
                           if i + j < len(lines) and lines[i + j] == ctx_line)
                           
        # Check if removed lines match after context
        removed_matches = sum(1 for j, rm_line in enumerate(lines_removed) 
                           if i + len(context_before) + j < len(lines) 
                           and lines[i + len(context_before) + j] == rm_line)
        
        # Calculate total match score
        match_score = (context_matches / max(1, len(context_before))) * 0.7 + \
                      (removed_matches / max(1, len(lines_removed))) * 0.3
                      
        # If this is the best match so far and it's reasonable
        if match_score > max_context_matched and match_score > 0.5:
            max_context_matched = match_score
            best_position = i
            
    # If we couldn't find a good match, try just near the target line
    if best_position is None:
        target_area_start = max(0, min(target_line, len(lines) - 1))
        search_radius = 10  # Look 10 lines before and after target
        
        for i in range(max(0, target_area_start - search_radius), 
                       min(len(lines), target_area_start + search_radius)):
            # Check if any context line matches at this position
            for ctx_line in context_before:
                if i < len(lines) and lines[i] == ctx_line:
                    best_position = i
                    break
            if best_position is not None:
                break
                
    # If still no match, use the target line from the patch
    if best_position is None:
        best_position = min(target_line, len(lines))
        
    # Apply the hunk
    # Copy lines up to the hunk position
    result_lines.extend(lines[:best_position])
    
    # Skip context before (already verified it matches)
    skip_lines = len(context_before) + len(lines_removed)
    
    # Add the new lines
    result_lines.extend(lines_added)
    
    # Continue with the rest of the file
    if best_position + skip_lines < len(lines):
        result_lines.extend(lines[best_position + skip_lines:])
        
    return '\n'.join(result_lines)

def try_fuzzy_patch(original_content: str, patch_content: str, file_path: str) -> Tuple[bool, str]:
    """
    Try to apply patch using a fuzzy matching algorithm for more flexible
    patching when contexts don't match exactly
    """
    try:
        # Try to import diff_match_patch if available
        try:
            from diff_match_patch import diff_match_patch
            dmp = diff_match_patch()
        except ImportError:
            logger.warning("diff_match_patch library not available for fuzzy patching")
            return False, original_content

        # Extract the changes (removing context) to create a simpler patch to apply
        simplified_patch = extract_simplified_changes(patch_content)
        if not simplified_patch:
            logger.warning(f"Failed to extract simplified changes for fuzzy patching")
            return False, original_content
            
        # Apply the patch using diff-match-patch
        patches = dmp.patch_fromText(simplified_patch)
        if not patches:
            logger.warning(f"Failed to create fuzzy patch")
            return False, original_content
            
        patched_content, results = dmp.patch_apply(patches, original_content)
        
        # Check if all patches were applied successfully
        if not all(results):
            logger.warning(f"Some fuzzy patches could not be applied: {results}")
            return False, original_content
            
        # Check if content changed
        if patched_content == original_content:
            logger.warning(f"Fuzzy patching did not modify content for {file_path}")
            return False, original_content
            
        logger.info(f"Successfully applied patch to {file_path} using fuzzy matching")
        return True, patched_content
        
    except Exception as e:
        logger.error(f"Error during fuzzy patching: {str(e)}")
        return False, original_content

def extract_simplified_changes(patch_content: str) -> str:
    """
    Extract just the core changes from a patch for fuzzy patching
    """
    # This is a simplified version; a real implementation would convert 
    # unified diff format to diff-match-patch format
    return patch_content

def commit_using_patch(repo_name: str, branch_name: str, file_paths: List[str], 
                      modified_contents: List[str], commit_message: str, 
                      expected_content: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Commit changes by generating and applying diffs rather than replacing entire files
    
    Args:
        repo_name: Repository name or full path
        branch_name: Branch to commit to
        file_paths: List of file paths to update
        modified_contents: List of modified content for each file path
        commit_message: Commit message
        expected_content: Optional dict mapping file paths to their expected content after patching
        
    Returns:
        Dictionary with status and metadata information
    """
    try:
        # Make sure we have matching lists
        if len(file_paths) != len(modified_contents):
            logger.error("File paths and modified contents must have the same length")
            return {
                "success": False, 
                "error": "Mismatched file paths and contents",
                "method": "none"
            }
            
        repo = get_repo(repo_name)
        if not repo:
            return {
                "success": False, 
                "error": "Could not access repository",
                "method": "none"
            }
            
        # Process one file at a time
        diffs = []
        file_changes = []
        patch_results = []
        
        for i, file_path in enumerate(file_paths):
            # Get the original content
            original_content = get_file_content(repo_name, file_path, branch_name)
            file_expected_content = expected_content.get(file_path) if expected_content else None
            
            if original_content is None:
                # File doesn't exist, so we'll create it
                logger.info(f"File {file_path} doesn't exist, will create it")
                file_changes.append({
                    'filename': file_path,
                    'content': modified_contents[i],
                    'action': 'create'
                })
                patch_results.append({
                    "file": file_path,
                    "method": "create_new",
                    "success": True,
                    "validation": file_expected_content == modified_contents[i] if file_expected_content else True
                })
                continue
                
            # Skip if no changes
            if original_content == modified_contents[i]:
                logger.info(f"No changes detected for {file_path}, skipping")
                patch_results.append({
                    "file": file_path,
                    "method": "no_changes",
                    "success": True,
                    "validation": True
                })
                continue
                
            # Generate a diff
            diff = generate_diff(original_content, modified_contents[i], file_path)
            diffs.append({
                'file_path': file_path,
                'diff': diff
            })
            
            # Try to apply the patch intelligently
            patched_content = original_content
            patch_success = False
            patch_method = "none"
            
            # Only attempt intelligent patching if we have a valid diff
            if diff and not diff.isspace() and len(diff) > 0:
                success, patched_content, method = apply_patch_to_content(
                    original_content, diff, file_path
                )
                patch_success = success
                patch_method = method
                
                # Verify the patched content against expected content if provided
                validation_passed = True
                if patch_success and file_expected_content:
                    # Compare ignoring whitespace differences
                    expected_normalized = '\n'.join(line.strip() for line in file_expected_content.splitlines())
                    patched_normalized = '\n'.join(line.strip() for line in patched_content.splitlines())
                    validation_passed = expected_normalized == patched_normalized
                    
                    if not validation_passed:
                        logger.warning(f"Patched content for {file_path} doesn't match expected content")
                        # If validation fails but we have expected content, use it
                        patched_content = file_expected_content
                        patch_method = "expected_fallback"
            else:
                logger.warning(f"Generated empty or invalid diff for {file_path}")
                patch_method = "empty_diff"
                
            # If intelligent patching failed or validation failed, fall back to direct replacement
            if not patch_success:
                logger.warning(f"Intelligent patching failed for {file_path}, falling back to direct file replacement")
                patched_content = modified_contents[i]
                patch_method = "direct_fallback"
                
            # Add the file change with the final content
            file_changes.append({
                'filename': file_path,
                'content': patched_content,
                'action': 'update'
            })
            
            # Record results for reporting
            patch_results.append({
                "file": file_path,
                "method": patch_method,
                "success": True,  # At this point we will commit something
                "validation": validation_passed if file_expected_content else True
            })
            
        # Log the diffs for debugging
        for diff_info in diffs:
            logger.info(f"Diff for {diff_info['file_path']}:")
            logger.info(diff_info['diff'][:200] + "..." if len(diff_info['diff']) > 200 else diff_info['diff'])
            
        # Commit the changes using the tree API for efficiency
        if file_changes:
            commit_success = commit_multiple_changes_as_tree(repo_name, branch_name, file_changes, commit_message)
            return {
                "success": commit_success,
                "patch_results": patch_results,
                "files_changed": len(file_changes)
            }
        else:
            logger.info("No changes to commit")
            return {
                "success": True,
                "message": "No changes detected to commit",
                "patch_results": patch_results,
                "files_changed": 0
            }
    except Exception as e:
        logger.error(f"Error committing using patch: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "method": "exception"
        }
