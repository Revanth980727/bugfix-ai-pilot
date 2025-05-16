
import os
import logging
import sys
from dotenv import load_dotenv

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-config")

# Load environment variables from root .env file
load_dotenv()

# GitHub configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO_OWNER = os.getenv('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.getenv('GITHUB_REPO_NAME')
GITHUB_DEFAULT_BRANCH = os.getenv('GITHUB_DEFAULT_BRANCH', 'main')
GITHUB_USE_DEFAULT_BRANCH_ONLY = os.getenv('GITHUB_USE_DEFAULT_BRANCH_ONLY', 'False').lower() == 'true'
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() == 'true'

def verify_config():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_REPO_OWNER': GITHUB_REPO_OWNER,
        'GITHUB_REPO_NAME': GITHUB_REPO_NAME
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        error_msg = f"Missing required GitHub environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        logger.error("Please check your .env file and ensure all required variables are set.")
        return False
        
    # Check if token is a placeholder
    if GITHUB_TOKEN == "your_github_token_here":
        logger.error("GITHUB_TOKEN contains a placeholder value. Please set a valid GitHub token in your .env file.")
        return False

    logger.info("GitHub configuration validated successfully")
    if DEBUG_MODE:
        logger.info(f"Owner: {GITHUB_REPO_OWNER}, Repo: {GITHUB_REPO_NAME}, Branch: {GITHUB_DEFAULT_BRANCH}")
        logger.info(f"Use default branch only: {GITHUB_USE_DEFAULT_BRANCH_ONLY}")
        logger.info(f"Test mode: {TEST_MODE}, Debug mode: {DEBUG_MODE}")
    
    return True

def get_repo_info():
    """Return repository information dictionary."""
    return {
        "owner": GITHUB_REPO_OWNER,
        "name": GITHUB_REPO_NAME,
        "default_branch": GITHUB_DEFAULT_BRANCH,
        "use_default_branch_only": GITHUB_USE_DEFAULT_BRANCH_ONLY
    }

def is_test_mode():
    """Check if running in test mode."""
    return TEST_MODE

def is_debug_mode():
    """Check if running in debug mode."""
    return DEBUG_MODE
