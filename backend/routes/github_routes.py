
import os
import json
import difflib
import logging
import re
import time
import hashlib
import tempfile
import subprocess
from flask import Blueprint, request, jsonify
from ..github_utils import get_file_content, generate_diff
from ..github_service.github_service import GitHubService
from ..github_service.utils import prepare_response_metadata, is_test_mode, is_production
from ..github_service.config import verify_config, get_repo_info
from ..log_utils import log_diff_summary, format_validation_result, create_structured_error

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-routes")

# Create blueprint for GitHub routes
github_bp = Blueprint('github', __name__, url_prefix='/api/github')

# Initialize GitHub service
github_service = None
try:
    github_service = GitHubService()
    logger.info("GitHub service initialized for routes")
except Exception as e:
    logger.error(f"Failed to initialize GitHub service: {str(e)}")

@github_bp.route('/config', methods=['GET'])
def get_github_config():
    """Get GitHub configuration from environment variables"""
    try:
        # Make sure config is valid first
        if not verify_config():
            return jsonify({
                'success': False,
                'error': 'GitHub configuration is invalid or incomplete'
            }), 500
            
        # Get GitHub configuration
        config = get_repo_info()
        config.update({
            'patch_mode': os.environ.get('PATCH_MODE', 'line-by-line'),
            'test_mode': is_test_mode(),
            'environment': os.environ.get('ENVIRONMENT', 'development')
        })
        
        return jsonify({
            'success': True,
            'config': config
        }), 200
    except Exception as e:
        logger.error(f"Error getting GitHub config: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to get GitHub config: {str(e)}"
        }), 500

@github_bp.route('/validate-diff', methods=['POST'])
def validate_diff():
    """Validate a diff to ensure it's properly formatted and applies cleanly"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
            
        # Extract required data
        diff_content = data.get('diff')
        file_path = data.get('file_path')
        
        if not diff_content:
            return jsonify({
                'success': False,
                'error': 'No diff content provided',
                'errorCode': 'MISSING_DIFF'
            }), 400
            
        # Basic syntax validation
        if not diff_content.startswith("@@") and not diff_content.startswith("---"):
            return jsonify({
                'success': False,
                'error': 'Invalid diff format - must start with @@ or ---',
                'errorCode': 'INVALID_DIFF_FORMAT'
            }), 400
            
        # Count lines added/removed
        lines_added = sum(1 for line in diff_content.splitlines() if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff_content.splitlines() if line.startswith('-') and not line.startswith('---'))
        
        # Validate using git if possible
        validation_result = {
            'valid': True,
            'lines_added': lines_added,
            'lines_removed': lines_removed,
            'syntax_valid': True
        }
        
        # Attempt advanced validation using git apply --check
        try:
            with tempfile.NamedTemporaryFile(suffix='.diff', mode='w') as diff_file:
                diff_file.write(diff_content)
                diff_file.flush()
                
                # Try to validate with git
                try:
                    result = subprocess.run(
                        ['git', 'apply', '--check', diff_file.name],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        validation_result['valid'] = False
                        validation_result['error'] = result.stderr
                        validation_result['errorCode'] = 'PATCH_APPLY_FAILED'
                except (subprocess.SubprocessError, FileNotFoundError):
                    # If git isn't available, fall back to basic validation
                    pass
        except Exception as e:
            logger.warning(f"Advanced diff validation failed: {str(e)}")
            # This is just extra validation, so continue even if it fails
            
        return jsonify({
            'success': True,
            'validation': validation_result
        }), 200
    except Exception as e:
        logger.error(f"Error validating diff: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to validate diff: {str(e)}",
            'errorCode': 'VALIDATION_ERROR'
        }), 500

@github_bp.route('/patch', methods=['POST'])
def create_patch():
    """Generate a patch for file changes"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
            
        # Extract required data
        repo_name = data.get('repo_name')
        branch = data.get('branch')
        file_path = data.get('file_path')
        modified_content = data.get('modified_content')
        
        if not all([repo_name, file_path, modified_content]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
            
        # Validate file path in production environment
        is_prod = is_production()
        test_mode = is_test_mode()
        
        if is_prod and not test_mode:
            if file_path.endswith('test.md') or '/test/' in file_path:
                logger.warning(f"Refusing to generate patch for test file in production: {file_path}")
                return jsonify({
                    'success': False,
                    'error': f'Cannot patch test files in production environment',
                    'errorCode': 'TEST_MODE_REQUIRED'
                }), 403
            
        # Get the original file content
        original_content = get_file_content(repo_name, file_path, branch)
        if original_content is None:
            return jsonify({
                'success': False,
                'error': f'File {file_path} not found',
                'errorCode': 'FILE_NOT_FOUND'
            }), 404
            
        # Generate a diff between the original and modified content
        diff = generate_diff(original_content, modified_content, file_path)
        
        # Check if the diff is empty (no actual changes)
        if not diff or diff.strip() == '':
            logger.warning(f"Generated empty diff for {file_path} - no changes detected")
            return jsonify({
                'success': False,
                'error': f'No changes detected between original and modified content',
                'errorCode': 'EMPTY_DIFF'
            }), 400
        
        # Calculate lines added and removed from the diff
        lines_added = sum(1 for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff.splitlines() if line.startswith('-') and not line.startswith('---'))
        
        # Calculate checksums for validation
        before_checksum = hashlib.md5(original_content.encode('utf-8')).hexdigest()
        after_checksum = hashlib.md5(modified_content.encode('utf-8')).hexdigest()
        
        # Log a preview of the generated diff
        diff_stats = log_diff_summary(logger, file_path, diff)
        
        return jsonify({
            'success': True,
            'diff': diff,
            'filename': file_path,
            'linesAdded': lines_added,
            'linesRemoved': lines_removed,
            'validation': {
                'beforeChecksum': before_checksum,
                'afterChecksum': after_checksum,
                'contentChanged': before_checksum != after_checksum,
                'beforeLines': len(original_content.splitlines()),
                'afterLines': len(modified_content.splitlines())
            },
            'diffStats': diff_stats
        }), 200
    except Exception as e:
        logger.error(f"Error generating patch: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to generate patch: {str(e)}"
        }), 500

@github_bp.route('/commit', methods=['POST'])
def commit_changes():
    """Commit changes to GitHub using patch-based updates"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
            
        # Extract required data
        repo_name = data.get('repo_name')
        branch = data.get('branch')
        file_changes = data.get('file_changes', [])
        commit_message = data.get('commit_message', 'Update files')
        patch_content = data.get('patch_content')
        
        if not all([repo_name, branch]) or (not file_changes and not patch_content):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        # Check environment configuration
        is_prod = is_production()
        test_mode = is_test_mode()
        logger.info(f"Environment: {'Production' if is_prod else 'Development'}, Test Mode: {test_mode}")
        
        # Extract file paths and contents
        file_paths = []
        modified_contents = []
        file_results = []
        
        # Process file changes from direct content updates
        if file_changes:
            for change in file_changes:
                if not change.get('filename') or not change.get('content'):
                    file_results.append({
                        "file_path": change.get('filename', 'unknown'),
                        "success": False,
                        "error": create_structured_error(
                            "VALIDATION_FAILED",
                            "Missing filename or content",
                            change.get('filename', 'unknown')
                        )
                    })
                    logger.warning(f"Rejected patch: Missing filename or content")
                    continue
                
                filename = change.get('filename')
                content = change.get('content')
                
                # Skip test files in production unless test_mode is enabled
                if is_prod and not test_mode and (filename.endswith('test.md') or '/test/' in filename):
                    file_results.append({
                        "file_path": filename,
                        "success": False,
                        "error": create_structured_error(
                            "TEST_MODE_REQUIRED",
                            "Test file in production",
                            filename,
                            "Enable test mode or use non-test file paths"
                        )
                    })
                    logger.warning(f"Skipping test file in production: {filename}")
                    continue
                    
                file_paths.append(filename)
                modified_contents.append(content)
                
                # Calculate file checksum for tracking
                if isinstance(content, str):
                    content_bytes = content.encode('utf-8')
                elif isinstance(content, dict):
                    content_bytes = json.dumps(content, sort_keys=True).encode('utf-8')
                else:
                    content_bytes = str(content).encode('utf-8')
                    
                file_results.append({
                    "file_path": filename,
                    "success": True,
                    "checksum": hashlib.md5(content_bytes).hexdigest()
                })
                
                logger.info(f"Validated patch for file: {filename} (MD5: {hashlib.md5(content_bytes).hexdigest()[:8]}...)")
            
        # Add timestamp to ensure changes are detected
        commit_message = f"{commit_message} - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Prepare initial metadata based on file validation results
        metadata = prepare_response_metadata(file_results)
        
        logger.info(f"Committing changes to {branch}: {len(file_paths)} files")
        
        # If we have a patch_content field, use that for patch-based commits
        if patch_content and github_service:
            patched_file_paths = data.get('patched_files', [])
            
            if not patched_file_paths:
                logger.warning("Patch content provided but no patched file paths specified")
                return jsonify({
                    'success': False,
                    'error': 'Patch content provided but no patched file paths specified',
                    'errorCode': 'MISSING_PATCHED_FILES',
                    'metadata': metadata
                }), 400
                
            logger.info(f"Using patch-based commit for {len(patched_file_paths)} files")
            
            # Skip test files in production unless test_mode is enabled
            if is_prod and not test_mode:
                filtered_paths = []
                for path in patched_file_paths:
                    if path.endswith('test.md') or '/test/' in path:
                        logger.warning(f"Skipping test file in production: {path}")
                        continue
                    filtered_paths.append(path)
                patched_file_paths = filtered_paths
            
            # Commit using patch content
            success, patch_metadata = github_service.commit_patch(
                branch,
                patch_content,
                commit_message,
                patched_file_paths
            )
            
            if success:
                # Update metadata with patch-specific information
                metadata.update(patch_metadata)
                
                return jsonify({
                    'success': True,
                    'message': f"Changes committed to branch {branch} using patch",
                    'branch': branch,
                    'files_changed': len(patched_file_paths),
                    'metadata': metadata
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': patch_metadata.get('error', 'Failed to apply patch'),
                    'errorCode': patch_metadata.get('code', 'PATCH_FAILED'),
                    'metadata': metadata
                }), 400
        
        # Skip commit if no valid patches
        if len(file_paths) == 0:
            logger.warning("No valid files to commit after filtering")
            return jsonify({
                'success': False,
                'error': 'No valid files to commit after filtering',
                'metadata': metadata
            }), 400
        
        # Use the GitHub service for the commit if available
        if github_service:
            success, commit_metadata = github_service.commit_bug_fix(
                branch,
                file_paths,
                modified_contents,
                "TICKET-ID",  # Replace with actual ticket ID if available
                commit_message
            )
            
            # Merge metadata from commit operation with our validation metadata
            if isinstance(commit_metadata, dict):
                # Update our metadata with any additional fields from commit_metadata
                for key, value in commit_metadata.items():
                    if key not in metadata or key == 'fileChecksums' or key == 'fileValidation':
                        metadata[key] = value
            
            # Handle case where no changes were actually made
            if not success:
                logger.warning("Commit operation completed but no changes were detected or applied")
                if "error" in commit_metadata:
                    error_info = commit_metadata["error"]
                    return jsonify({
                        'success': False,
                        'error': error_info.get("message", "No changes were detected after patch application"),
                        'errorCode': error_info.get("code", "COMMIT_EMPTY"),
                        'metadata': metadata
                    }), 400
                else:
                    return jsonify({
                        'success': False,
                        'error': 'No changes were detected after patch application',
                        'errorCode': 'COMMIT_EMPTY',
                        'metadata': metadata
                    }), 400
        else:
            # Fallback to the original method
            from ..github_utils import commit_using_patch
            logger.warning("GitHub service not available, falling back to basic commit method")
            success = commit_using_patch(repo_name, branch, file_paths, modified_contents, commit_message)
            if success:
                metadata["changesVerified"] = True
        
        if success:
            return jsonify({
                'success': True,
                'message': f"Changes committed to branch {branch}",
                'branch': branch,
                'files_changed': len(file_paths),
                'metadata': metadata
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to commit changes',
                'errorCode': metadata.get('error', {}).get('code', 'COMMIT_FAILED') if isinstance(metadata.get('error'), dict) else 'COMMIT_FAILED',
                'metadata': metadata
            }), 500
    except Exception as e:
        logger.error(f"Error committing changes: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to commit changes: {str(e)}",
            'errorCode': 'UNKNOWN_ERROR',
            'metadata': {
                'error': str(e),
                'errorType': type(e).__name__
            }
        }), 500

# ... keep existing code (file, PR creation, and comment routes)
