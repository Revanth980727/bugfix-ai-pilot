
import logging
import json
from flask import Blueprint, request, jsonify, current_app
from ..jira_service.jira_service import JiraService
from ..log_utils import log_operation_attempt, log_operation_result, get_error_metadata, GitHubOperationError
import asyncio

# Configure logging
logger = logging.getLogger("jira-routes")

# Create blueprint for Jira routes
jira_bp = Blueprint('jira', __name__, url_prefix='/api/jira')

# Initialize Jira service
jira_service = None
try:
    jira_service = JiraService()
    logger.info("Jira service initialized")
except Exception as e:
    logger.error(f"Failed to initialize Jira service: {str(e)}")

@jira_bp.route('/tickets', methods=['GET'])
def get_tickets():
    """Get tickets from Jira"""
    try:
        if not jira_service:
            return jsonify({'error': 'Jira service not initialized'}), 500
            
        # Get query parameters
        ticket_id = request.args.get('ticket_id')
        status = request.args.get('status')
        
        # Get tickets based on parameters - using async properly
        if ticket_id:
            tickets = asyncio.run(jira_service.get_ticket(ticket_id))
            if not tickets:
                return jsonify({'error': f'Ticket {ticket_id} not found'}), 404
        elif status:
            tickets = asyncio.run(jira_service.get_tickets_by_status(status))
        else:
            tickets = asyncio.run(jira_service.get_all_tickets())
            
        # Return tickets
        return jsonify({'tickets': tickets}), 200
    except Exception as e:
        logger.error(f"Error getting tickets: {str(e)}")
        return jsonify({'error': f'Failed to get tickets: {str(e)}'}), 500
        
@jira_bp.route('/tickets/<ticket_id>/update', methods=['POST'])
def update_ticket_status():
    """Update ticket status"""
    try:
        if not jira_service:
            return jsonify({'error': 'Jira service not initialized'}), 500
            
        # Get ticket ID and data
        ticket_id = request.view_args.get('ticket_id')
        data = request.json
        
        if not ticket_id or not data:
            return jsonify({'error': 'Missing ticket ID or update data'}), 400
            
        # Extract update fields
        status = data.get('status')
        comment = data.get('comment')
        escalation = data.get('escalation')
        error_message = data.get('error_message')
        github_metadata = data.get('github_metadata', {})
        
        # Log GitHub operation if present
        if github_metadata:
            log_operation_attempt(logger, "PR creation for ticket", {
                "ticket_id": ticket_id, 
                "github_metadata": github_metadata
            })
        
        # Update ticket - properly awaiting the async operation
        result = asyncio.run(jira_service.update_ticket(
            ticket_id,
            status=status,
            comment=comment,
            escalation=escalation,
            error_message=error_message,
            github_metadata=github_metadata
        ))
        
        # Log a successful GitHub operation result
        if github_metadata:
            log_operation_result(logger, "PR creation for ticket", True, {
                "ticket_id": ticket_id, 
                "status_updated": status is not None,
                "comment_added": comment is not None
            })
        
        # Return result
        return jsonify({
            'success': True,
            'message': f'Ticket {ticket_id} updated',
            'result': result
        }), 200
    except GitHubOperationError as e:
        # Handle GitHub-specific errors
        logger.error(f"GitHub operation error for ticket update: {e.message}")
        logger.error(f"Error metadata: {json.dumps(e.metadata, default=str)}")
        
        if e.original_exception:
            logger.error(f"Original error: {str(e.original_exception)}")
            
        # Log failed GitHub operation
        log_operation_result(logger, e.operation, False, e.metadata)
        
        return jsonify({
            'success': False,
            'error': f'GitHub operation failed: {e.message}',
            'metadata': e.metadata
        }), 500
    except Exception as e:
        logger.error(f"Error updating ticket: {str(e)}")
        error_metadata = get_error_metadata(e)
        
        return jsonify({
            'success': False,
            'error': f'Failed to update ticket: {str(e)}',
            'metadata': error_metadata
        }), 500

@jira_bp.route('/tickets/<ticket_id>/comment', methods=['POST'])
def add_ticket_comment():
    """Add a comment to a ticket"""
    try:
        if not jira_service:
            return jsonify({'error': 'Jira service not initialized'}), 500
            
        # Get ticket ID and data
        ticket_id = request.view_args.get('ticket_id')
        data = request.json
        
        if not ticket_id or not data:
            return jsonify({'error': 'Missing ticket ID or comment data'}), 400
            
        # Extract comment text
        comment = data.get('comment')
        
        if not comment:
            return jsonify({'error': 'Missing comment text'}), 400
            
        # Add comment to ticket - properly awaiting the async operation
        result = asyncio.run(jira_service.add_comment(ticket_id, comment))
        
        # Return result
        return jsonify({
            'success': True,
            'message': f'Comment added to ticket {ticket_id}',
            'result': result
        }), 200
    except Exception as e:
        logger.error(f"Error adding comment to ticket: {str(e)}")
        error_metadata = get_error_metadata(e)
        
        return jsonify({
            'success': False,
            'error': f'Failed to add comment: {str(e)}',
            'metadata': error_metadata
        }), 500

@jira_bp.route('/config', methods=['GET'])
def get_jira_config():
    """Get Jira configuration"""
    try:
        # Return basic Jira config info (non-sensitive)
        config = {
            'jira_enabled': bool(jira_service),
            'jira_url': jira_service.url if jira_service else None,
            'jira_project': jira_service.project if jira_service else None
        }
        
        return jsonify({
            'success': True,
            'config': config
        }), 200
    except Exception as e:
        logger.error(f"Error getting Jira config: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to get Jira config: {str(e)}'
        }), 500
