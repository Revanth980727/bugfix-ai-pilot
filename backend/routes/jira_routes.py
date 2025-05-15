
import os
import json
import logging
from flask import Blueprint, request, jsonify
from ..jira_service.jira_service import JiraService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jira-routes")

# Create blueprint for Jira routes
jira_bp = Blueprint('jira', __name__, url_prefix='/api/jira')

# Initialize Jira service
jira_service = None
try:
    jira_service = JiraService()
    logger.info("Jira service initialized for routes")
except Exception as e:
    logger.error(f"Failed to initialize Jira service: {str(e)}")

@jira_bp.route('/config', methods=['GET'])
def get_jira_config():
    """Get Jira configuration from environment variables"""
    try:
        # Get Jira configuration
        config = {
            'jira_url': os.environ.get('JIRA_URL', ''),
            'jira_project': os.environ.get('JIRA_PROJECT', ''),
            'test_mode': os.environ.get('JIRA_TEST_MODE', 'false').lower() == 'true',
            'environment': os.environ.get('ENVIRONMENT', 'development')
        }
        
        # Don't include auth-related values like username/token
        
        return jsonify({
            'success': True,
            'config': config
        }), 200
    except Exception as e:
        logger.error(f"Error getting Jira config: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to get Jira config: {str(e)}"
        }), 500

@jira_bp.route('/ticket/<ticket_id>', methods=['GET'])
def get_ticket_details(ticket_id):
    """Get details for a specific ticket"""
    try:
        if not jira_service:
            return jsonify({
                'success': False,
                'error': 'Jira service not initialized'
            }), 503
            
        # Get ticket details from Jira
        ticket = jira_service.get_ticket(ticket_id)
        
        if not ticket:
            return jsonify({
                'success': False,
                'error': f'Ticket {ticket_id} not found'
            }), 404
            
        # Simplify the response to just the essential fields
        simplified_ticket = {
            'id': ticket.get('id'),
            'key': ticket.get('key'),
            'summary': ticket.get('fields', {}).get('summary', ''),
            'description': ticket.get('fields', {}).get('summary', ''),
            'status': ticket.get('fields', {}).get('status', {}).get('name', '')
        }
            
        return jsonify({
            'success': True,
            'ticket': simplified_ticket
        }), 200
    except Exception as e:
        logger.error(f"Error getting ticket {ticket_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to get ticket details: {str(e)}"
        }), 500

@jira_bp.route('/ticket/<ticket_id>/status', methods=['PUT'])
def update_ticket_status(ticket_id):
    """Update the status of a Jira ticket"""
    try:
        if not jira_service:
            return jsonify({
                'success': False,
                'error': 'Jira service not initialized'
            }), 503
            
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
            
        status = data.get('status')
        comment = data.get('comment')
        
        if not status:
            return jsonify({
                'success': False,
                'error': 'No status provided'
            }), 400
            
        # Update the ticket status
        success = jira_service.update_ticket_status(ticket_id, status, comment)
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'Failed to update ticket {ticket_id} status'
            }), 500
            
        return jsonify({
            'success': True,
            'message': f'Ticket {ticket_id} status updated to {status}'
        }), 200
    except Exception as e:
        logger.error(f"Error updating ticket {ticket_id} status: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to update ticket status: {str(e)}"
        }), 500

@jira_bp.route('/ticket/<ticket_id>/comment', methods=['POST'])
def add_ticket_comment(ticket_id):
    """Add a comment to a Jira ticket"""
    try:
        if not jira_service:
            return jsonify({
                'success': False,
                'error': 'Jira service not initialized'
            }), 503
            
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
            
        comment = data.get('comment')
        
        if not comment:
            return jsonify({
                'success': False,
                'error': 'No comment provided'
            }), 400
            
        # Add the comment
        success = jira_service.add_comment(ticket_id, comment)
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'Failed to add comment to ticket {ticket_id}'
            }), 500
            
        return jsonify({
            'success': True,
            'message': f'Comment added to ticket {ticket_id}'
        }), 200
    except Exception as e:
        logger.error(f"Error adding comment to ticket {ticket_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to add comment: {str(e)}"
        }), 500

@jira_bp.route('/ticket/<ticket_id>/pr', methods=['POST'])
def link_pr_to_ticket(ticket_id):
    """Link a pull request to a Jira ticket and update status"""
    try:
        if not jira_service:
            return jsonify({
                'success': False,
                'error': 'Jira service not initialized'
            }), 503
            
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
            
        pr_url = data.get('pr_url')
        pr_number = data.get('pr_number')
        qa_passed = data.get('qa_passed', True)  # Default to passing if not specified
        comment = data.get('comment')
        
        if not pr_url:
            return jsonify({
                'success': False,
                'error': 'No PR URL provided'
            }), 400
            
        if not pr_number:
            # Try to extract PR number from URL
            import re
            match = re.search(r'/pull/(\d+)', pr_url)
            if match:
                pr_number = int(match.group(1))
            else:
                pr_number = 0
                
        # Update the ticket with PR info
        success = jira_service.update_ticket_with_pr(ticket_id, pr_url, pr_number, qa_passed, comment)
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'Failed to link PR to ticket {ticket_id}'
            }), 500
            
        return jsonify({
            'success': True,
            'message': f'PR linked to ticket {ticket_id}',
            'status_updated': True,
            'new_status': 'In Review' if qa_passed else 'QA Failed'
        }), 200
    except Exception as e:
        logger.error(f"Error linking PR to ticket {ticket_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to link PR: {str(e)}"
        }), 500
