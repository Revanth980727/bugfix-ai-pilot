
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
JIRA_API_TOKEN = os.getenv('JIRA_TOKEN') or os.getenv('JIRA_API_TOKEN')
JIRA_USERNAME = os.getenv('JIRA_USER') or os.getenv('JIRA_USERNAME')
JIRA_URL = os.getenv('JIRA_URL')
JIRA_PROJECT_KEY = os.getenv('JIRA_PROJECT_KEY', '')
JIRA_POLL_INTERVAL = int(os.getenv('JIRA_POLL_INTERVAL', '30'))

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')

# Application configuration
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '4'))
PROJECT_TEST_COMMAND = os.getenv('PROJECT_TEST_COMMAND', 'npm test')
LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '30'))
RETRY_DELAY_SECONDS = int(os.getenv('RETRY_DELAY_SECONDS', '5'))

# Log configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

def verify_env_vars():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'JIRA_API_TOKEN': JIRA_API_TOKEN,
        'JIRA_USERNAME': JIRA_USERNAME,
        'JIRA_URL': JIRA_URL,
        'OPENAI_API_KEY': OPENAI_API_KEY
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please check your .env file and ensure all required variables are set."
        )
    
    print(f"Environment verified: All required variables are set")
    print(f"JIRA configuration: URL={JIRA_URL}, User={JIRA_USERNAME}, Project={JIRA_PROJECT_KEY}")
    print(f"JIRA poll interval: {JIRA_POLL_INTERVAL} seconds")
    print(f"GitHub configuration: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")

# Added GitHub repo verification function
def verify_github_repo_settings():
    """Verify that GitHub repository settings are properly configured."""
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is missing"
    
    # Check if we're using repo_owner/repo_name pattern
    if GITHUB_REPO_OWNER and GITHUB_REPO_NAME:
        return True, f"GitHub repository configured as {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
    
    return False, "GITHUB_REPO_OWNER and GITHUB_REPO_NAME are required for GitHub operations"

# Debug function to print all environment variables (without secrets)
def print_env_debug():
    """Print environment variables for debugging (without showing secrets)."""
    print("\n=== Environment Configuration ===")
    print(f"JIRA_URL: {JIRA_URL}")
    print(f"JIRA_USERNAME: {'Set' if JIRA_USERNAME else 'Not set'}")
    print(f"JIRA_API_TOKEN: {'Set' if JIRA_API_TOKEN else 'Not set'}")
    print(f"JIRA_PROJECT_KEY: {JIRA_PROJECT_KEY}")
    print(f"JIRA_POLL_INTERVAL: {JIRA_POLL_INTERVAL}")
    print(f"GITHUB_REPO_OWNER: {GITHUB_REPO_OWNER}")
    print(f"GITHUB_REPO_NAME: {GITHUB_REPO_NAME}")
    print(f"GITHUB_DEFAULT_BRANCH: {GITHUB_DEFAULT_BRANCH}")
    print(f"OPENAI_MODEL: {OPENAI_MODEL}")
    print(f"MAX_RETRIES: {MAX_RETRIES}")
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print("================================\n")

