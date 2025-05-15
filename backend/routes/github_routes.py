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
            'patch_mode': os.environ.get('PATCH_MODE', 'line-by-line')
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
            
        # Get the original file content
        original_content = get_file_content(repo_name, file_path, branch)
        if original_content is None:
            return jsonify({
                'success': False,
                'error': f'File {file_path} not found'
            }), 404
            
        # Generate a diff between the original and modified content
        diff = generate_diff(original_content, modified_content, file_path)
        
        # Calculate lines added and removed from the diff
        lines_added = sum(1 for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff.splitlines() if line.startswith('-') and not line.startswith('---'))
        
        logger.info(f"Generated diff for {file_path}: {lines_added} lines added, {lines_removed} lines removed")
        
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
                continue
            
            filename = change.get('filename')
            content = change.get('content')
            
            # Skip test files in production
            if os.environ.get('ENVIRONMENT') == 'production' and (filename.endswith('test.md') or '/test/' in filename):
                logger.info(f"Skipping test file in production: {filename}")
                continue
                
            file_paths.append(filename)
            modified_contents.append(content)
            metadata['fileList'].append(filename)
            
            # Add file checksum for validation
            import hashlib
            metadata['fileChecksums'][filename] = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            metadata['validationDetails']['validPatches'] += 1
            
        # Add timestamp to ensure changes are detected
        commit_message = f"{commit_message} - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        logger.info(f"Committing changes to {branch}: {len(file_paths)} files")
        
        # Use the GitHub service for the commit if available
        if github_service:
            result = github_service.commit_bug_fix(
                branch,
                file_paths,
                modified_contents,
                "TICKET-ID",  # Replace with actual ticket ID if available
                commit_message
            )
        else:
            # Fallback to the original method
            from ..github_utils import commit_using_patch
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
            'error': f"Failed to commit changes: {str(e)}"
        }), 500

@github_bp.route('/file', methods=['GET'])
def get_file():
    """Get the content of a file from GitHub"""
    try:
        repo_name = request.args.get('repo')
        file_path = request.args.get('path')
        branch = request.args.get('branch')
        
        if not all([repo_name, file_path]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
            
        # Get the file content
        content = get_file_content(repo_name, file_path, branch)
        if content is None:
            return jsonify({
                'success': False,
                'error': f'File {file_path} not found'
            }), 404
            
        return jsonify({
            'success': True,
            'content': content,
            'file_path': file_path
        }), 200
    except Exception as e:
        logger.error(f"Error getting file content: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to get file content: {str(e)}"
        }), 500

@github_bp.route('/create-pr', methods=['POST'])
def create_pr():
    """Create a pull request for the fix"""
    try:
        if not github_service:
            logger.error("GitHub service not initialized")
            return jsonify({
                'success': False,
                'error': 'GitHub service not initialized'
            }), 500
        
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Extract required data
        ticket_id = data.get('ticket_id')
        branch_name = data.get('branch_name')
        title = data.get('title', f"Fix for {ticket_id}")
        description = data.get('description', f"This PR fixes the issue described in {ticket_id}")
        base_branch = data.get('base_branch')
        
        if not all([ticket_id, branch_name]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters (ticket_id, branch_name)'
            }), 400
        
        logger.info(f"Creating PR for branch {branch_name}, ticket {ticket_id}")
        
        # Create PR using the GitHub service
        pr_result = github_service.create_fix_pr(
            branch_name=branch_name,
            ticket_id=ticket_id,
            title=title,
            description=description,
            base_branch=base_branch
        )
        
        if not pr_result:
            logger.error(f"Failed to create PR for ticket {ticket_id}")
            return jsonify({
                'success': False,
                'error': 'Failed to create PR'
            }), 500
        
        # Get PR URL and number from the result
        pr_url = pr_result.get('url')
        pr_number = pr_result.get('number')
        
        logger.info(f"Successfully created PR #{pr_number} at {pr_url} for ticket {ticket_id}")
        
        return jsonify({
            'success': True,
            'pr_url': pr_url,
            'pr_number': pr_number,
            'message': f"PR created successfully for ticket {ticket_id}"
        }), 201
    except Exception as e:
        logger.error(f"Error creating PR: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to create PR: {str(e)}"
        }), 500

@github_bp.route('/add-comment', methods=['POST'])
def add_comment():
    """Add a comment to a PR"""
    try:
        if not github_service:
            return jsonify({
                'success': False,
                'error': 'GitHub service not initialized'
            }), 500
        
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Extract required data
        pr_identifier = data.get('pr_identifier')
        comment = data.get('comment')
        
        if not all([pr_identifier, comment]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters (pr_identifier, comment)'
            }), 400
        
        # Handle case where pr_identifier might be a tuple
        if isinstance(pr_identifier, tuple) and len(pr_identifier) > 0:
            logger.info(f"Received PR identifier as tuple: {pr_identifier}")
            # If it's a tuple like (URL, number), use the number
            if len(pr_identifier) > 1 and isinstance(pr_identifier[1], int):
                pr_identifier = pr_identifier[1]
                logger.info(f"Using PR number {pr_identifier} from tuple")
            else:
                pr_identifier = pr_identifier[0]
                logger.info(f"Using first element of tuple as PR identifier: {pr_identifier}")
        
        # Add comment to PR
        success = github_service.add_pr_comment(pr_identifier, comment)
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'Failed to add comment to PR {pr_identifier}'
            }), 500
        
        return jsonify({
            'success': True,
            'message': f"Comment added to PR {pr_identifier}",
        }), 200
    except Exception as e:
        logger.error(f"Error adding comment: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to add comment: {str(e)}"
        }), 500
