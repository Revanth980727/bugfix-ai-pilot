
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# GitHub configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# JIRA configuration
JIRA_TOKEN = os.getenv('JIRA_TOKEN')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_URL = os.getenv('JIRA_URL')

def verify_env_vars():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'JIRA_TOKEN': JIRA_TOKEN,
        'JIRA_USER': JIRA_USER,
        'JIRA_URL': JIRA_URL
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please check your .env file and ensure all required variables are set."
        )

