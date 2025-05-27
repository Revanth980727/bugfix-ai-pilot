
import os
import sys
import logging
from typing import Dict, Any, Optional, List, Tuple

class EnvironmentValidator:
    """Centralized environment variable loader and validator"""
    
    def __init__(self):
        self.logger = logging.getLogger("env-validator")
        self.variables = {}
        self._load_variables()
    
    def _load_variables(self):
        """Load all environment variables into a dictionary"""
        # GitHub configuration
        self.variables["GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN")
        self.variables["GITHUB_REPO_OWNER"] = os.getenv("GITHUB_REPO_OWNER")
        self.variables["GITHUB_REPO_NAME"] = os.getenv("GITHUB_REPO_NAME")
        self.variables["GITHUB_DEFAULT_BRANCH"] = os.getenv("GITHUB_DEFAULT_BRANCH", "main")
        self.variables["GITHUB_USE_DEFAULT_BRANCH_ONLY"] = os.getenv("GITHUB_USE_DEFAULT_BRANCH_ONLY", "False").lower() == "true"
        
        # JIRA configuration
        self.variables["JIRA_API_TOKEN"] = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_TOKEN")
        self.variables["JIRA_USERNAME"] = os.getenv("JIRA_USERNAME") or os.getenv("JIRA_USER")
        self.variables["JIRA_URL"] = os.getenv("JIRA_URL")
        self.variables["JIRA_PROJECT_KEY"] = os.getenv("JIRA_PROJECT_KEY", "")
        self.variables["JIRA_POLL_INTERVAL"] = int(os.getenv("JIRA_POLL_INTERVAL", "30"))
        
        # OpenAI configuration
        self.variables["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
        self.variables["OPENAI_MODEL"] = os.getenv("OPENAI_MODEL", "gpt-4o")
        
        # Application configuration
        self.variables["MAX_RETRIES"] = int(os.getenv("MAX_RETRIES", "4"))
        self.variables["RETRY_DELAY_SECONDS"] = int(os.getenv("RETRY_DELAY_SECONDS", "5"))
        self.variables["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "INFO")
        
        # Testing/debugging configuration
        self.variables["TEST_MODE"] = os.getenv("TEST_MODE", "False").lower() == "true"
        self.variables["DEBUG_MODE"] = os.getenv("DEBUG_MODE", "False").lower() == "true"
        
        # Log important configuration values
        if self.variables["TEST_MODE"]:
            self.logger.warning("⚠️ TEST_MODE is enabled - using mocked services!")
            self.logger.warning("Set TEST_MODE=False in .env for real service interactions")
        
        if self.variables["DEBUG_MODE"]:
            self.logger.info("Debug mode is enabled")
    
    def validate_environment(self, required_groups: List[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate that all required environment variables are set.
        
        Args:
            required_groups: List of groups to validate ('github', 'jira', 'openai', 'all')
            
        Returns:
            Tuple of (is_valid, missing_variables)
        """
        missing_vars = []
        placeholder_vars = []
        groups_to_check = required_groups or ["all"]
        
        # Define required variables by group
        requirements = {
            "github": ["GITHUB_TOKEN", "GITHUB_REPO_OWNER", "GITHUB_REPO_NAME"],
            "jira": ["JIRA_API_TOKEN", "JIRA_USERNAME", "JIRA_URL"],
            "openai": ["OPENAI_API_KEY"]
        }
        
        # Define placeholder values to check against
        placeholders = {
            "GITHUB_TOKEN": "your_github_token_here",
            "GITHUB_REPO_OWNER": "your_github_username_or_org",
            "GITHUB_REPO_NAME": "your_repository_name",
            "JIRA_API_TOKEN": "your_jira_token_here",
            "JIRA_USERNAME": "your_jira_email_here",
            "JIRA_URL": "your_jira_url_here",
            "OPENAI_API_KEY": "your_openai_api_key_here"
        }
        
        # Check all groups if 'all' is specified
        if "all" in groups_to_check:
            groups_to_check = ["github", "jira", "openai"]
        
        # Validate each group
        for group in groups_to_check:
            if group not in requirements:
                self.logger.warning(f"Unknown validation group: {group}")
                continue
                
            for var in requirements[group]:
                # Check if variable is missing
                if not self.variables.get(var):
                    missing_vars.append(var)
                # Check if variable has placeholder value
                elif var in placeholders and self.variables.get(var) == placeholders[var]:
                    placeholder_vars.append(var)
        
        # Log results
        if missing_vars:
            self.logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        if placeholder_vars and not self.variables.get("TEST_MODE", False):
            self.logger.error(f"Placeholder values detected for: {', '.join(placeholder_vars)}")
            self.logger.error("Please replace placeholder values with real credentials in .env file")
            # If not in test mode, consider placeholder values as invalid
            missing_vars.extend(placeholder_vars)
        elif placeholder_vars:
            self.logger.warning(f"Placeholder values detected for: {', '.join(placeholder_vars)}")
            self.logger.warning("Running with placeholder values only works in TEST_MODE")
        
        is_valid = len(missing_vars) == 0
        
        if is_valid:
            self.logger.info("All required environment variables are set")
        
        return is_valid, missing_vars
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key with optional default"""
        return self.variables.get(key, default)
    
    def get_github_config(self) -> Dict[str, Any]:
        """Get all GitHub configuration as a dictionary"""
        return {
            "token": self.variables.get("GITHUB_TOKEN"),
            "owner": self.variables.get("GITHUB_REPO_OWNER"),
            "repo": self.variables.get("GITHUB_REPO_NAME"),
            "default_branch": self.variables.get("GITHUB_DEFAULT_BRANCH"),
            "use_default_branch_only": self.variables.get("GITHUB_USE_DEFAULT_BRANCH_ONLY", False),
            "test_mode": self.variables.get("TEST_MODE", False)
        }
    
    def get_jira_config(self) -> Dict[str, Any]:
        """Get all JIRA configuration as a dictionary"""
        return {
            "token": self.variables.get("JIRA_API_TOKEN"),
            "username": self.variables.get("JIRA_USERNAME"),
            "url": self.variables.get("JIRA_URL"),
            "project_key": self.variables.get("JIRA_PROJECT_KEY"),
            "poll_interval": self.variables.get("JIRA_POLL_INTERVAL")
        }

# Singleton instance
env_validator = EnvironmentValidator()

def get_config() -> EnvironmentValidator:
    """Get the singleton environment validator instance"""
    return env_validator

def validate_required_config(groups: List[str] = None) -> bool:
    """Validate that all required environment variables for specified groups are set"""
    valid, missing = env_validator.validate_environment(groups)
    if not valid:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Please check your .env file and ensure all required variables are set.")
        return False
    return True

# Convenience function for direct access to environment variables
def get_env(key: str, default: Any = None) -> Any:
    """Get a configuration value by key with optional default"""
    return env_validator.get(key, default)

# Function to check if we're in test mode
def is_test_mode() -> bool:
    """Check if the application is running in test mode"""
    return env_validator.get("TEST_MODE", False)

# Function to check if GitHub configuration is valid for real interactions
def has_valid_github_config(allow_test_mode: bool = False) -> bool:
    """
    Check if GitHub configuration is valid for real interactions
    
    Args:
        allow_test_mode: If True, test mode is considered valid
        
    Returns:
        True if configuration is valid, False otherwise
    """
    # If test mode is allowed, don't validate as strictly
    if allow_test_mode and env_validator.get("TEST_MODE", False):
        return True
        
    # Check for required variables
    token = env_validator.get("GITHUB_TOKEN")
    owner = env_validator.get("GITHUB_REPO_OWNER")
    repo = env_validator.get("GITHUB_REPO_NAME")
    
    # Check if variables are present
    if not (token and owner and repo):
        return False
        
    # Check if variables contain placeholder values
    if token == "your_github_token_here":
        return False
        
    if owner == "your_github_username_or_org":
        return False
        
    if repo == "your_repository_name":
        return False
        
    return True

# Print debug function
def print_environment_summary():
    """Print a summary of the environment configuration"""
    print("\n===== Environment Configuration =====")
    
    # GitHub configuration
    print("GitHub Configuration:")
    github_config = env_validator.get_github_config()
    print(f"  Repository: {github_config['owner']}/{github_config['repo']}")
    print(f"  Default Branch: {github_config['default_branch']}")
    print(f"  Token Present: {'Yes' if github_config['token'] else 'No'}")
    print(f"  Use Default Branch Only: {'Yes' if github_config['use_default_branch_only'] else 'No'}")
    print(f"  Test Mode: {'Yes' if github_config['test_mode'] else 'No'}")
    
    # JIRA configuration
    print("\nJIRA Configuration:")
    jira_config = env_validator.get_jira_config()
    print(f"  URL: {jira_config['url'] or 'Not set'}")
    print(f"  Username Present: {'Yes' if jira_config['username'] else 'No'}")
    print(f"  Token Present: {'Yes' if jira_config['token'] else 'No'}")
    print(f"  Project Key: {jira_config['project_key'] or 'Not set'}")
    print(f"  Poll Interval: {jira_config['poll_interval']} seconds")
    
    # Other configuration
    print("\nOther Configuration:")
    print(f"  TEST_MODE: {'Enabled' if env_validator.get('TEST_MODE') else 'Disabled'}")
    print(f"  DEBUG_MODE: {'Enabled' if env_validator.get('DEBUG_MODE') else 'Disabled'}")
    print(f"  MAX_RETRIES: {env_validator.get('MAX_RETRIES')}")
    print(f"  LOG_LEVEL: {env_validator.get('LOG_LEVEL')}")
    print("===================================\n")
