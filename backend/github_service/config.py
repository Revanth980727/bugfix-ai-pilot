
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
# Explicitly handle the TEST_MODE value as a boolean with safer default to False
TEST_MODE = os.getenv('TEST_MODE', 'False').lower() in ('true', 'yes', '1', 't')
# Add configuration for empty commit handling
ALLOW_EMPTY_COMMITS = os.getenv('ALLOW_EMPTY_COMMITS', 'False').lower() in ('true', 'yes', '1', 't')
# Add configuration for branch case sensitivity
PRESERVE_BRANCH_CASE = os.getenv('PRESERVE_BRANCH_CASE', 'True').lower() in ('true', 'yes', '1', 't')
# Add configuration for including test files in commits
INCLUDE_TEST_FILES = os.getenv('INCLUDE_TEST_FILES', 'False').lower() in ('true', 'yes', '1', 't')

# Patch processing configuration
PATCH_MODE = os.getenv('PATCH_MODE', 'line-by-line')

def detect_placeholder_values():
    """Detect placeholder values in GitHub configuration."""
    placeholders = []
    
    if GITHUB_TOKEN == "your_github_token_here":
        placeholders.append("GITHUB_TOKEN")
    if GITHUB_REPO_OWNER == "your_github_username_or_org":
        placeholders.append("GITHUB_REPO_OWNER")
    if GITHUB_REPO_NAME == "your_repository_name":
        placeholders.append("GITHUB_REPO_NAME")
    
    return placeholders

def verify_config():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_REPO_OWNER': GITHUB_REPO_OWNER,
        'GITHUB_REPO_NAME': GITHUB_REPO_NAME
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    placeholder_vars = detect_placeholder_values()
    
    # Check for missing variables
    if missing_vars:
        error_msg = f"Missing required GitHub environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        logger.error("Please check your .env file and ensure all required variables are set.")
        
        # Only allow missing vars in test mode
        if not TEST_MODE:
            logger.error("Running in PRODUCTION mode with incomplete configuration - this will cause failures!")
            return False
        else:
            logger.warning("Running in TEST_MODE with incomplete configuration (not recommended)")
    else:
        logger.info("All required GitHub variables are present")
    
    # Check for placeholder values
    if placeholder_vars:
        error_msg = f"GitHub configuration contains placeholder values: {', '.join(placeholder_vars)}"
        logger.error(error_msg)
        logger.error("Please set real values in your .env file.")
        
        if not TEST_MODE:
            logger.error("Using placeholder values in PRODUCTION mode will cause authentication failures!")
            return False
        else:
            logger.warning("Using placeholder values only allowed in TEST_MODE")

    # Check for empty string values
    empty_vars = [var for var, value in required_vars.items() if value == ""]
    if empty_vars:
        logger.error(f"GitHub variables set to empty strings: {', '.join(empty_vars)}")
        if not TEST_MODE:
            logger.error("Empty values in PRODUCTION mode will cause failures!")
            return False

    # Explicitly check if we're in test mode and warn about it
    if TEST_MODE:
        logger.warning("⚠️ Running in TEST_MODE - using mock GitHub integration!")
        logger.warning("Set TEST_MODE=False in .env for real GitHub interactions")
        
        # In test mode, provide fallback values for placeholder/missing config
        if not GITHUB_REPO_OWNER or GITHUB_REPO_OWNER == "your_github_username_or_org":
            logger.warning("Using fallback GitHub owner 'test-org' for TEST_MODE")
        if not GITHUB_REPO_NAME or GITHUB_REPO_NAME == "your_repository_name":
            logger.warning("Using fallback GitHub repo 'test-repo' for TEST_MODE")
    else:
        logger.info("✅ Using real GitHub integration (TEST_MODE is off)")

    # Log configuration values for debugging
    logger.info("GitHub configuration validated successfully")
    if DEBUG_MODE:
        logger.info(f"Owner: {GITHUB_REPO_OWNER}, Repo: {GITHUB_REPO_NAME}, Branch: {GITHUB_DEFAULT_BRANCH}")
        logger.info(f"Use default branch only: {GITHUB_USE_DEFAULT_BRANCH_ONLY}")
        logger.info(f"Test mode: {TEST_MODE}, Debug mode: {DEBUG_MODE}")
        logger.info(f"Patch mode: {PATCH_MODE}")
        logger.info(f"Allow empty commits: {ALLOW_EMPTY_COMMITS}")
        logger.info(f"Preserve branch case: {PRESERVE_BRANCH_CASE}")
        logger.info(f"Include test files: {INCLUDE_TEST_FILES}")
    
    return True

def get_repo_info():
    """Return repository information dictionary with fallbacks for test mode."""
    # Use fallback values in test mode if placeholders are detected
    owner = GITHUB_REPO_OWNER
    name = GITHUB_REPO_NAME
    
    if TEST_MODE:
        if not owner or owner == "your_github_username_or_org":
            owner = "test-org"
        if not name or name == "your_repository_name":
            name = "test-repo"
    
    return {
        "owner": owner,
        "name": name,
        "default_branch": GITHUB_DEFAULT_BRANCH,
        "use_default_branch_only": GITHUB_USE_DEFAULT_BRANCH_ONLY,
        "patch_mode": PATCH_MODE,
        "allow_empty_commits": ALLOW_EMPTY_COMMITS,
        "preserve_branch_case": PRESERVE_BRANCH_CASE,
        "include_test_files": INCLUDE_TEST_FILES
    }

def get_repo_string():
    """Get the repository string in 'owner/name' format with test mode fallbacks."""
    repo_info = get_repo_info()
    owner = repo_info["owner"]
    name = repo_info["name"]
    
    if not owner or not name:
        logger.warning("Cannot create repo string - owner or name missing from environment")
        return None
    
    repo_string = f"{owner}/{name}"
    
    if TEST_MODE and (owner == "test-org" or name == "test-repo"):
        logger.warning(f"Using test mode repository string: {repo_string}")
    
    return repo_string

# ... keep existing code (other configuration functions)

def validate_github_urls():
    """Validate that GitHub URLs will be real, not placeholders."""
    repo_string = get_repo_string()
    
    if not repo_string:
        return False, "No repository configuration available"
    
    # Check for test/placeholder patterns
    if "test-org" in repo_string or "test-repo" in repo_string:
        if not TEST_MODE:
            return False, f"Placeholder repository '{repo_string}' not allowed in production"
        else:
            return True, f"Using test repository '{repo_string}' (TEST_MODE enabled)"
    
    # Check for common placeholder patterns
    placeholder_patterns = ["example", "your-", "placeholder", "demo"]
    for pattern in placeholder_patterns:
        if pattern in repo_string.lower():
            warning_msg = f"Repository '{repo_string}' appears to contain placeholder text"
            if not TEST_MODE:
                return False, warning_msg + " - not allowed in production"
            else:
                logger.warning(warning_msg + " - allowed in TEST_MODE")
    
    return True, f"Repository '{repo_string}' appears valid"

# Enhanced configuration check that includes URL validation
def verify_github_integration():
    """Comprehensive GitHub integration verification."""
    logger.info("Verifying GitHub integration configuration...")
    
    # Basic config check
    config_valid = verify_config()
    if not config_valid:
        logger.error("Basic GitHub configuration failed")
        return False
    
    # URL validation
    url_valid, url_message = validate_github_urls()
    if not url_valid:
        logger.error(f"GitHub URL validation failed: {url_message}")
        return False
    else:
        logger.info(f"GitHub URL validation passed: {url_message}")
    
    # Module availability check
    try:
        import github
        logger.info("PyGithub module is available")
    except ImportError:
        logger.error("PyGithub module not installed - run: pip install PyGithub")
        if not TEST_MODE:
            return False
    
    # diff-match-patch availability check
    try:
        import diff_match_patch
        logger.info("diff-match-patch module is available")
    except ImportError:
        logger.warning("diff-match-patch module not installed - some patch features will be degraded")
        logger.warning("Run: pip install diff-match-patch")
    
    logger.info("✅ GitHub integration verification completed successfully")
    return True

# New function to get safe URLs for production use
def get_safe_github_url(path=""):
    """Get a GitHub URL that's safe for production use."""
    repo_string = get_repo_string()
    
    if not repo_string:
        if TEST_MODE:
            repo_string = "test-org/test-repo"
        else:
            raise ValueError("No valid repository configuration for URL generation")
    
    base_url = f"https://github.com/{repo_string}"
    
    if path:
        return f"{base_url}/{path}"
    
    return base_url
