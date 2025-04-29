
import os
from dotenv import load_dotenv

# Load environment variables from root .env file
load_dotenv()

# GitHub configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO_OWNER = os.getenv('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.getenv('GITHUB_REPO_NAME')
GITHUB_DEFAULT_BRANCH = os.getenv('GITHUB_DEFAULT_BRANCH', 'main')

# JIRA configuration
JIRA_TOKEN = os.getenv('JIRA_TOKEN')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_URL = os.getenv('JIRA_URL')

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Application configuration
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '4'))
PROJECT_TEST_COMMAND = os.getenv('PROJECT_TEST_COMMAND', 'npm test')
LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '30'))
RETRY_DELAY_SECONDS = int(os.getenv('RETRY_DELAY_SECONDS', '5'))

def verify_env_vars():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'JIRA_TOKEN': JIRA_TOKEN,
        'JIRA_USER': JIRA_USER,
        'JIRA_URL': JIRA_URL,
        'OPENAI_API_KEY': OPENAI_API_KEY
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please check your .env file and ensure all required variables are set."
        )

# Added GitHub repo verification function
def verify_github_repo_settings():
    """Verify that GitHub repository settings are properly configured."""
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is missing"
    
    # Check if we're using repo_owner/repo_name pattern
    if GITHUB_REPO_OWNER and GITHUB_REPO_NAME:
        return True, f"GitHub repository configured as {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
    
    return False, "GITHUB_REPO_OWNER and GITHUB_REPO_NAME are required for GitHub operations"
