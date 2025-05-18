
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

# Patch processing configuration
PATCH_MODE = os.getenv('PATCH_MODE', 'line-by-line')

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
        
    # Check if repo owner/name are placeholders
    if GITHUB_REPO_OWNER == "your_github_username_or_org":
        logger.error("GITHUB_REPO_OWNER contains a placeholder value. Please set a valid GitHub username or organization in your .env file.")
        return False
        
    if GITHUB_REPO_NAME == "your_repository_name":
        logger.error("GITHUB_REPO_NAME contains a placeholder value. Please set a valid repository name in your .env file.")
        return False

    # Check if repo owner/name are empty strings
    if GITHUB_REPO_OWNER == "":
        logger.error("GITHUB_REPO_OWNER is an empty string. Please set a valid GitHub username or organization in your .env file.")
        return False
        
    if GITHUB_REPO_NAME == "":
        logger.error("GITHUB_REPO_NAME is an empty string. Please set a valid repository name in your .env file.")
        return False

    # Explicitly check if we're in test mode and warn about it
    if TEST_MODE:
        logger.warning("⚠️ Running in TEST_MODE - using mock GitHub integration!")
        logger.warning("Set TEST_MODE=False in .env for real GitHub interactions")
    else:
        logger.info("✅ Using real GitHub integration (TEST_MODE is off)")

    # Log configuration values for debugging
    logger.info("GitHub configuration validated successfully")
    if DEBUG_MODE:
        logger.info(f"Owner: {GITHUB_REPO_OWNER}, Repo: {GITHUB_REPO_NAME}, Branch: {GITHUB_DEFAULT_BRANCH}")
        logger.info(f"Use default branch only: {GITHUB_USE_DEFAULT_BRANCH_ONLY}")
        logger.info(f"Test mode: {TEST_MODE}, Debug mode: {DEBUG_MODE}")
        logger.info(f"Patch mode: {PATCH_MODE}")
    
    return True

def get_repo_info():
    """Return repository information dictionary."""
    return {
        "owner": GITHUB_REPO_OWNER,
        "name": GITHUB_REPO_NAME,
        "default_branch": GITHUB_DEFAULT_BRANCH,
        "use_default_branch_only": GITHUB_USE_DEFAULT_BRANCH_ONLY,
        "patch_mode": PATCH_MODE
    }

def is_test_mode():
    """Check if running in test mode."""
    return TEST_MODE

def is_debug_mode():
    """Check if running in debug mode."""
    return DEBUG_MODE

# Export explicit repo string for consistent usage
def get_repo_string():
    """Get the repository string in 'owner/name' format."""
    if not GITHUB_REPO_OWNER or not GITHUB_REPO_NAME:
        logger.warning("Cannot create repo string - owner or name missing from environment")
        return None
    return f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"

# Get patch mode configuration
def get_patch_mode():
    """Get the configured patch mode."""
    return PATCH_MODE
