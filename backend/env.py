
import os
import logging
import traceback
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
ALLOW_EMPTY_COMMITS = os.getenv('ALLOW_EMPTY_COMMITS', 'False').lower() in ('true', 'yes', '1', 't')

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

# Test mode and debug settings - explicitly handle string vs boolean
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() in ('true', 'yes', '1', 't')
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() in ('true', 'yes', '1', 't')

# Log configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# For backward compatibility - use consistently named vars
# These are now deprecated but kept for backward compatibility
JIRA_USER = JIRA_USERNAME
JIRA_TOKEN = JIRA_API_TOKEN

# Log important config details with enhanced validation
if TEST_MODE:
    logger.warning("⚠️ TEST_MODE is enabled - using mock GitHub and JIRA integrations")
    logger.warning("To use real services, set TEST_MODE=False in .env")
else:
    logger.info("✅ Production mode enabled - using real GitHub and JIRA integrations")

def validate_placeholder_values():
    """Check for common placeholder values in environment variables."""
    placeholder_issues = []
    
    # GitHub placeholders
    if GITHUB_TOKEN == "your_github_token_here":
        placeholder_issues.append("GITHUB_TOKEN contains placeholder 'your_github_token_here'")
    if GITHUB_REPO_OWNER == "your_github_username_or_org":
        placeholder_issues.append("GITHUB_REPO_OWNER contains placeholder 'your_github_username_or_org'")
    if GITHUB_REPO_NAME == "your_repository_name":
        placeholder_issues.append("GITHUB_REPO_NAME contains placeholder 'your_repository_name'")
    
    # JIRA placeholders
    if JIRA_API_TOKEN == "your_jira_api_token_here":
        placeholder_issues.append("JIRA_API_TOKEN contains placeholder 'your_jira_api_token_here'")
    if JIRA_USERNAME == "your_jira_email_here":
        placeholder_issues.append("JIRA_USERNAME contains placeholder 'your_jira_email_here'")
    if JIRA_URL == "https://your-domain.atlassian.net":
        placeholder_issues.append("JIRA_URL contains placeholder 'https://your-domain.atlassian.net'")
    
    # OpenAI placeholders
    if OPENAI_API_KEY == "your_openai_api_key_here":
        placeholder_issues.append("OPENAI_API_KEY contains placeholder 'your_openai_api_key_here'")
    
    return placeholder_issues

def verify_env_vars():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_REPO_OWNER': GITHUB_REPO_OWNER,
        'GITHUB_REPO_NAME': GITHUB_REPO_NAME,
        'JIRA_API_TOKEN': JIRA_API_TOKEN,
        'JIRA_USERNAME': JIRA_USERNAME,
        'JIRA_URL': JIRA_URL,
        'OPENAI_API_KEY': OPENAI_API_KEY
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    placeholder_issues = validate_placeholder_values()
    
    # Check for empty string values (different from None/missing)
    empty_vars = [var for var, value in required_vars.items() if value == ""]
    if empty_vars:
        logger.error(f"Environment variables set to empty strings: {', '.join(empty_vars)}")
        logger.error("Empty string values will cause authentication failures")
    
    # Report missing variables
    if missing_vars and not TEST_MODE:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}\n"
        error_msg += "Please check your .env file and ensure all required variables are set."
        logger.error(error_msg)
        raise EnvironmentError(error_msg)
    elif missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)} (ignored in TEST_MODE)")
    
    # Report placeholder values
    if placeholder_issues and not TEST_MODE:
        error_msg = "Environment configuration contains placeholder values:\n"
        for issue in placeholder_issues:
            error_msg += f"- {issue}\n"
        error_msg += "Please update your .env file with real values"
        logger.error(error_msg)
        raise ValueError(error_msg)
    elif placeholder_issues:
        for issue in placeholder_issues:
            logger.warning(f"{issue} (allowed only in TEST_MODE)")
    
    # Enhanced JIRA URL validation
    if JIRA_URL:
        if JIRA_URL.endswith('/'):
            logger.warning(f"JIRA_URL ends with a slash: {JIRA_URL}")
            logger.warning("This might cause double slashes in API calls")
        
        if not JIRA_URL.startswith('https://'):
            logger.warning(f"JIRA_URL should start with 'https://': {JIRA_URL}")
    
    # Log successful validation
    logger.info(f"Environment verified: All required variables are set")
    logger.info(f"JIRA configuration: URL={JIRA_URL}, User={JIRA_USERNAME}, Project={JIRA_PROJECT_KEY}")
    logger.info(f"JIRA poll interval: {JIRA_POLL_INTERVAL} seconds")
    logger.info(f"GitHub configuration: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}")
    logger.info(f"GitHub empty commits allowed: {ALLOW_EMPTY_COMMITS}")
    logger.info(f"Test mode: {'Enabled' if TEST_MODE else 'Disabled'}")

# ... keep existing code (GitHub repo verification, JIRA settings, debug functions, module verification, Python path checking)

def verify_required_modules():
    """Verify that all required Python modules are available, including diff-match-patch."""
    required_modules = {
        'github': 'PyGithub',
        'jira': 'jira',
        'unidiff': 'unidiff',
        'dotenv': 'python-dotenv',
        'requests': 'requests',
        'diff_match_patch': 'diff-match-patch',  # Add the new dependency
    }
    
    missing_modules = []
    available_modules = []
    
    for module_name, package_name in required_modules.items():
        try:
            __import__(module_name)
            available_modules.append(module_name)
            logger.debug(f"Module {module_name} is installed")
        except ImportError:
            missing_modules.append(f"{module_name} (pip install {package_name})")
            logger.error(f"Required module {module_name} is not installed")
    
    # Log results
    if available_modules:
        logger.info(f"Available modules: {', '.join(available_modules)}")
    
    if missing_modules:
        error_msg = f"Missing Python modules: {', '.join(missing_modules)}"
        logger.error(error_msg)
        logger.error("Install missing modules with: pip install -r requirements.txt")
        
        if not TEST_MODE:
            raise ImportError(error_msg)
        else:
            logger.warning("Running in TEST_MODE with missing modules (mock implementations will be used)")
    else:
        logger.info("✅ All required Python modules are available")
    
    return len(missing_modules) == 0

# Enhanced logging for troubleshooting
def log_environment_status():
    """Log comprehensive environment status for troubleshooting."""
    logger.info("=== ENVIRONMENT STATUS ===")
    
    # Test mode status
    logger.info(f"Test Mode: {'ON' if TEST_MODE else 'OFF'}")
    logger.info(f"Debug Mode: {'ON' if DEBUG_MODE else 'OFF'}")
    
    # Service configurations
    github_status = "CONFIGURED" if GITHUB_TOKEN and GITHUB_REPO_OWNER and GITHUB_REPO_NAME else "INCOMPLETE"
    jira_status = "CONFIGURED" if JIRA_API_TOKEN and JIRA_USERNAME and JIRA_URL else "INCOMPLETE"
    openai_status = "CONFIGURED" if OPENAI_API_KEY else "MISSING"
    
    logger.info(f"GitHub: {github_status}")
    logger.info(f"JIRA: {jira_status}")
    logger.info(f"OpenAI: {openai_status}")
    
    # Placeholder detection
    placeholder_issues = validate_placeholder_values()
    if placeholder_issues:
        logger.warning(f"Placeholder values detected: {len(placeholder_issues)} issues")
        for issue in placeholder_issues[:3]:  # Show first 3
            logger.warning(f"  - {issue}")
        if len(placeholder_issues) > 3:
            logger.warning(f"  ... and {len(placeholder_issues) - 3} more")
    else:
        logger.info("No placeholder values detected")
    
    logger.info("=== END STATUS ===")

# ... keep existing code (other verification functions)
