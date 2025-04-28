
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GitHub configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO_OWNER = os.getenv('GITHUB_REPO_OWNER')
GITHUB_REPO_NAME = os.getenv('GITHUB_REPO_NAME')
GITHUB_DEFAULT_BRANCH = os.getenv('GITHUB_DEFAULT_BRANCH', 'main')

def verify_config():
    """Verify that all required environment variables are set."""
    required_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_REPO_OWNER': GITHUB_REPO_OWNER,
        'GITHUB_REPO_NAME': GITHUB_REPO_NAME
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required GitHub environment variables: {', '.join(missing_vars)}\n"
            "Please check your .env file and ensure all required variables are set."
        )

    return True
