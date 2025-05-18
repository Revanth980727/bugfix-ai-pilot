
import os
import logging
from dotenv import load_dotenv

# Load environment variables from root .env file
load_dotenv()

# Setup logger
logger = logging.getLogger("env-manager")

# GitHub configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO_OWNER = os.getenv('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.getenv('GITHUB_REPO_NAME')
GITHUB_DEFAULT_BRANCH = os.getenv('GITHUB_DEFAULT_BRANCH', 'main')
GITHUB_USE_DEFAULT_BRANCH_ONLY = os.getenv('GITHUB_USE_DEFAULT_BRANCH_ONLY', 'False').lower() == 'true'

# JIRA configuration - standardize naming
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN') or os.getenv('JIRA_TOKEN')
JIRA_USERNAME = os.getenv('JIRA_USERNAME') or os.getenv('JIRA_USER')
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

# Test mode and debug settings
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() == 'true'
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

# Log configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# For backward compatibility - use consistently named vars
# These are now deprecated but kept for backward compatibility
JIRA_USER = JIRA_USERNAME
JIRA_TOKEN = JIRA_API_TOKEN

# Log important config details
if TEST_MODE:
    logger.warning("⚠️ TEST_MODE is enabled - using mock GitHub and JIRA integrations")
    logger.warning("To use real services, set TEST_MODE=False in .env")

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
    
    # Also check for placeholder values
    placeholder_issues = []
    if GITHUB_TOKEN == "your_github_token_here":
        placeholder_issues.append("GITHUB_TOKEN contains a placeholder value")
    if GITHUB_REPO_OWNER == "your_github_username_or_org":
        placeholder_issues.append("GITHUB_REPO_OWNER contains a placeholder value")
    if GITHUB_REPO_NAME == "your_repository_name":
        placeholder_issues.append("GITHUB_REPO_NAME contains a placeholder value")
    
    # Report issues
    if missing_vars and not TEST_MODE:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}\n"
        error_msg += "Please check your .env file and ensure all required variables are set."
        raise EnvironmentError(error_msg)
    elif missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)} (ignored in TEST_MODE)")
    
    if placeholder_issues and not TEST_MODE:
        error_msg = "Environment configuration contains placeholder values:\n"
        for issue in placeholder_issues:
            error_msg += f"- {issue}\n"
        error_msg += "Please update your .env file with real values"
        raise ValueError(error_msg)
    elif placeholder_issues:
        for issue in placeholder_issues:
            logger.warning(f"{issue} (allowed only in TEST_MODE)")
    
    # Validate JIRA_URL format - ensure it doesn't end with a double slash
    if JIRA_URL and JIRA_URL.endswith('/'):
        logger.warning(f"Warning: JIRA_URL ends with a slash. This might cause double slashes in API calls.")
    
    logger.info(f"Environment verified: All required variables are set")
    logger.info(f"JIRA configuration: URL={JIRA_URL}, User={JIRA_USERNAME}, Project={JIRA_PROJECT_KEY}")
    logger.info(f"JIRA poll interval: {JIRA_POLL_INTERVAL} seconds")
    logger.info(f"GitHub configuration: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
    logger.info(f"Test mode: {'Enabled' if TEST_MODE else 'Disabled'}")

# Added GitHub repo verification function
def verify_github_repo_settings():
    """Verify that GitHub repository settings are properly configured."""
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is missing"
    
    if GITHUB_TOKEN == "your_github_token_here" and not TEST_MODE:
        return False, "GITHUB_TOKEN contains a placeholder value"
    
    # Check if we're using repo_owner/repo_name pattern
    if GITHUB_REPO_OWNER and GITHUB_REPO_NAME:
        # Check for placeholder values
        if GITHUB_REPO_OWNER == "your_github_username_or_org" and not TEST_MODE:
            return False, "GITHUB_REPO_OWNER contains a placeholder value"
            
        if GITHUB_REPO_NAME == "your_repository_name" and not TEST_MODE:
            return False, "GITHUB_REPO_NAME contains a placeholder value"
        
        use_default_only = "only using default branch" if GITHUB_USE_DEFAULT_BRANCH_ONLY else "allowing branch creation"
        
        if TEST_MODE:
            return True, f"GitHub repository configured as {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME} ({use_default_only}) [TEST MODE]"
        else:
            return True, f"GitHub repository configured as {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME} ({use_default_only})"
    
    return False, "GITHUB_REPO_OWNER and GITHUB_REPO_NAME are required for GitHub operations"

# New function to verify Jira configuration
def verify_jira_settings():
    """Verify that JIRA settings are properly configured."""
    if not JIRA_API_TOKEN:
        return False, "JIRA_API_TOKEN is missing"
        
    if not JIRA_USERNAME:
        return False, "JIRA_USERNAME is missing"
        
    if not JIRA_URL:
        return False, "JIRA_URL is missing"
        
    # Check for placeholder values
    if JIRA_API_TOKEN == "your_jira_api_token_here" and not TEST_MODE:
        return False, "JIRA_API_TOKEN contains a placeholder value"
        
    if JIRA_USERNAME == "your_jira_email_here" and not TEST_MODE:
        return False, "JIRA_USERNAME contains a placeholder value"
        
    if JIRA_URL == "https://your-domain.atlassian.net" and not TEST_MODE:
        return False, "JIRA_URL contains a placeholder value"
        
    # Validate URL format
    if JIRA_URL.endswith('/'):
        logger.warning("JIRA_URL ends with a slash, which may cause API path issues")
        
    if TEST_MODE:
        return True, f"JIRA configured with URL={JIRA_URL}, User={JIRA_USERNAME} [TEST MODE]"
    else:
        return True, f"JIRA configured with URL={JIRA_URL}, User={JIRA_USERNAME}"

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
    print(f"GITHUB_USE_DEFAULT_BRANCH_ONLY: {GITHUB_USE_DEFAULT_BRANCH_ONLY}")
    print(f"TEST_MODE: {TEST_MODE}")
    print(f"DEBUG_MODE: {DEBUG_MODE}")
    print(f"OPENAI_MODEL: {OPENAI_MODEL}")
    print(f"MAX_RETRIES: {MAX_RETRIES}")
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print("================================\n")
