
import os
import json
import difflib
import logging
import re
import time
from flask import Blueprint, request, jsonify
from ..github_utils import get_file_content, generate_diff
from ..github_service.github_service import GitHubService

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
        # Get GitHub configuration
        config = {
            'repo_owner': os.environ.get('GITHUB_REPO_OWNER', ''),
            'repo_name': os.environ.get('GITHUB_REPO_NAME', ''),
            'default_branch': os.environ.get('GITHUB_DEFAULT_BRANCH', 'main'),
            'branch': os.environ.get('GITHUB_BRANCH', ''),
            'patch_mode': os.environ.get('PATCH_MODE', 'line-by-line'),
            'test_mode': os.environ.get('GITHUB_TEST_MODE', 'false').lower() == 'true',
            'environment': os.environ.get('ENVIRONMENT', 'development')
        }
        
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
        is_production = os.environ.get('ENVIRONMENT', 'development') == 'production'
        test_mode = os.environ.get('GITHUB_TEST_MODE', 'false').lower() == 'true'
        
        if is_production and not test_mode:
            if file_path.endswith('test.md') or '/test/' in file_path:
                logger.warning(f"Refusing to generate patch for test file in production: {file_path}")
                return jsonify({
                    'success': False,
                    'error': f'Cannot patch test files in production environment'
                }), 403
            
        # Get the original file content
        original_content = get_file_content(repo_name, file_path, branch)
        if original_content is None:
            return jsonify({
                'success': False,
                'error': f'File {file_path} not found'
            }), 404
            
        # Generate a diff between the original and modified content
        diff = generate_diff(original_content, modified_content, file_path)
        
        # Check if the diff is empty (no actual changes)
        if not diff or diff.strip() == '':
            logger.warning(f"Generated empty diff for {file_path} - no changes detected")
            return jsonify({
                'success': False,
                'error': f'No changes detected between original and modified content'
            }), 400
        
        # Calculate lines added and removed from the diff
        lines_added = sum(1 for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff.splitlines() if line.startswith('-') and not line.startswith('---'))
        
        # Log a preview of the generated diff
        max_log_length = 500
        diff_preview = diff[:max_log_length]
        if len(diff) > max_log_length:
            diff_preview += f"... [{len(diff) - max_log_length} more characters]"
        logger.info(f"Generated diff for {file_path}:\n{diff_preview}")
        logger.info(f"Diff stats for {file_path}: {lines_added} lines added, {lines_removed} lines removed")
        
        return jsonify({
            'success': True,
            'diff': diff,
            'filename': file_path,
            'linesAdded': lines_added,
            'linesRemoved': lines_removed
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
        
        if not all([repo_name, branch, file_changes]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        # Check environment configuration
        is_production = os.environ.get('ENVIRONMENT', 'development') == 'production'
        test_mode = os.environ.get('GITHUB_TEST_MODE', 'false').lower() == 'true'
        logger.info(f"Environment: {'Production' if is_production else 'Development'}, Test Mode: {test_mode}")
        
        # Prepare metadata for validation and response
        metadata = {
            'fileList': [],
            'totalFiles': len(file_changes),
            'fileChecksums': {},
            'validationDetails': {
                'totalPatches': len(file_changes),
                'validPatches': 0,
                'rejectedPatches': 0,
                'rejectionReasons': {}
            }
        }
            
        # Extract file paths and contents
        file_paths = []
        modified_contents = []
        
        for change in file_changes:
            if not change.get('filename') or not change.get('content'):
                metadata['validationDetails']['rejectedPatches'] += 1
                reason = 'Missing filename or content'
                metadata['validationDetails']['rejectionReasons'][reason] = metadata['validationDetails']['rejectionReasons'].get(reason, 0) + 1
                logger.warning(f"Rejected patch: {reason}")
                continue
            
            filename = change.get('filename')
            content = change.get('content')
            
            # Skip test files in production unless test_mode is enabled
            if is_production and not test_mode and (filename.endswith('test.md') or '/test/' in filename):
                metadata['validationDetails']['rejectedPatches'] += 1
                reason = 'Test file in production'
                metadata['validationDetails']['rejectionReasons'][reason] = metadata['validationDetails']['rejectionReasons'].get(reason, 0) + 1
                logger.warning(f"Skipping test file in production: {filename}")
                continue
                
            file_paths.append(filename)
            modified_contents.append(content)
            metadata['fileList'].append(filename)
            
            # Add file checksum for validation
            import hashlib
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            elif isinstance(content, dict):
                content_bytes = json.dumps(content).encode('utf-8')
            else:
                content_bytes = str(content).encode('utf-8')
                
            metadata['fileChecksums'][filename] = hashlib.md5(content_bytes).hexdigest()
            
            metadata['validationDetails']['validPatches'] += 1
            logger.info(f"Validated patch for file: {filename} (MD5: {metadata['fileChecksums'][filename][:8]}...)")
            
        # Add timestamp to ensure changes are detected
        commit_message = f"{commit_message} - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        logger.info(f"Committing changes to {branch}: {len(file_paths)} files")
        logger.info(f"Validation summary: {metadata['validationDetails']['validPatches']} valid, {metadata['validationDetails']['rejectedPatches']} rejected")
        
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
            result = github_service.commit_bug_fix(
                branch,
                file_paths,
                modified_contents,
                "TICKET-ID",  # Replace with actual ticket ID if available
                commit_message
            )
            
            # Handle case where no changes were actually made
            if not result:
                logger.warning("Commit operation completed but no changes were detected or applied")
                metadata['validationDetails']['additionalInfo'] = "No changes were detected after patch application"
                return jsonify({
                    'success': False,
                    'error': 'No changes were detected after patch application',
                    'metadata': metadata
                }), 400
        else:
            # Fallback to the original method
            from ..github_utils import commit_using_patch
            logger.warning("GitHub service not available, falling back to basic commit method")
            result = commit_using_patch(repo_name, branch, file_paths, modified_contents, commit_message)
        
        if result:
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
                'metadata': metadata
            }), 500
    except Exception as e:
        logger.error(f"Error committing changes: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to commit changes: {str(e)}",
            'metadata': {
                'error': str(e),
                'errorType': type(e).__name__
            }
        }), 500

# ... keep existing code (file, PR creation, and comment routes)
