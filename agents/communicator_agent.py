
import os
import json
from typing import Dict, Any, Optional
from .utils.logger import Logger
from .utils.jira_client import JiraClient
from .utils.github_client import GitHubClient

class CommunicatorAgent:
    """
    Agent responsible for communicating with external systems like JIRA and GitHub.
    Updates JIRA tickets with comments and progress, and creates PRs in GitHub.
    """
    
    def __init__(self):
        """Initialize the communicator agent"""
        self.logger = Logger("communicator_agent")
        
        # Initialize clients
        try:
            self.jira_client = JiraClient()
            self.github_client = GitHubClient()
        except Exception as e:
            self.logger.error(f"Error initializing API clients: {str(e)}")
            raise
            
    def run(self, communication_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute communication tasks based on the results of previous agents
        
        Args:
            communication_task: Dictionary with task details:
                {
                    "ticket_id": "PROJ-123",
                    "patch_data": { patch details from DeveloperAgent },
                    "test_results": { test results from QAAgent },
                    "task_plan": { task plan from PlannerAgent }
                }
                
        Returns:
            Dictionary with results:
            {
                "jira_updated": true/false,
                "pr_created": true/false,
                "pr_url": "URL if created",
                "comments_added": ["list", "of", "comments"],
                "ticket_status": "new status"
            }
        """
        ticket_id = communication_task.get("ticket_id", "unknown")
        self.logger.start_task(f"Communication tasks for ticket {ticket_id}")
        
        # Extract data from communication task
        patch_data = communication_task.get("patch_data", {})
        test_results = communication_task.get("test_results", {})
        task_plan = communication_task.get("task_plan", {})
        
        # Check if tests passed
        tests_passed = test_results.get("passed", False)
        
        # Get attempt number if available
        attempt = patch_data.get("attempt", 1)
        max_retries = communication_task.get("max_retries", 4)
        
        result = {
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
        }
        
        try:
            if tests_passed:
                # Tests passed - update JIRA and create PR
                result = self._handle_successful_fix(
                    ticket_id, patch_data, test_results, task_plan, attempt
                )
            else:
                # Tests failed - handle based on retry status
                result = self._handle_failed_fix(
                    ticket_id, patch_data, test_results, task_plan, attempt, max_retries
                )
                
            self.logger.end_task(f"Communication for ticket {ticket_id}", success=True)
            return result
            
        except Exception as e:
            self.logger.error(f"Communication tasks failed: {str(e)}")
            self.logger.end_task(f"Communication for ticket {ticket_id}", success=False)
            
            result["error"] = str(e)
            return result
            
    def _handle_successful_fix(
        self, 
        ticket_id: str, 
        patch_data: Dict[str, Any], 
        test_results: Dict[str, Any],
        task_plan: Dict[str, Any],
        attempt: int
    ) -> Dict[str, Any]:
        """Handle successful fix by creating PR and updating JIRA"""
        self.logger.info(f"Handling successful fix for ticket {ticket_id}")
        
        result = {
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
        }
        
        # 1. Create a branch for the fix
        branch_name = f"bugfix/{ticket_id.lower()}"
        self.logger.info(f"Creating branch {branch_name}")
        
        branch_created = self.github_client.create_branch(branch_name)
        if not branch_created:
            self.logger.error(f"Failed to create branch {branch_name}")
            return result
            
        # 2. Commit the changes
        commit_message = patch_data.get("commit_message", f"Fix bug {ticket_id}")
        if not commit_message.startswith(f"Fix {ticket_id}"):
            commit_message = f"Fix {ticket_id}: {commit_message}"
            
        patched_files = patch_data.get("patched_files", [])
        patch_content = patch_data.get("patch_content", "")
        
        # Apply the patch via GitHub API
        commit_success = self.github_client.commit_patch(
            branch_name=branch_name,
            patch_content=patch_content,
            commit_message=commit_message,
            patch_file_paths=patched_files
        )
        
        if not commit_success:
            self.logger.error("Failed to commit changes")
            
            # Update JIRA with error
            comment = (
                f"✅ A fix was generated but could not be committed to GitHub.\n\n"
                f"Fix attempt {attempt} was successful, but there was an issue committing the changes."
            )
            self.jira_client.add_comment(ticket_id, comment)
            result["comments_added"].append(comment)
            
            return result
            
        # 3. Create a PR
        self.logger.info("Creating pull request")
        
        pr_title = f"Fix {ticket_id}"
        
        # Create a detailed PR description
        fix_approach = task_plan.get("approach", "")
        root_cause = task_plan.get("root_cause", "")
        
        pr_body = (
            f"## Fix for {ticket_id}\n\n"
            f"### Root Cause\n{root_cause}\n\n"
            f"### Fix Approach\n{fix_approach}\n\n"
            f"### Changes Made\n"
        )
        
        for file_path in patched_files:
            pr_body += f"- Modified `{file_path}`\n"
            
        pr_body += f"\n### Test Results\n"
        pr_body += f"✅ All tests passed in {test_results.get('execution_time', 0):.2f} seconds\n"
        
        if "test_coverage" in test_results:
            pr_body += f"📊 Test coverage: {test_results['test_coverage']}%\n"
            
        pr_body += f"\n*This PR was created automatically by BugFix AI*"
        
        # Create the PR
        pr_url = self.github_client.create_pull_request(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=None  # Use default
        )
        
        if not pr_url:
            self.logger.error("Failed to create pull request")
            
            # Update JIRA with error
            comment = (
                f"✅ A fix was generated and committed to branch `{branch_name}`, "
                f"but there was an issue creating the pull request."
            )
            self.jira_client.add_comment(ticket_id, comment)
            result["comments_added"].append(comment)
            
            return result
            
        # 4. Update JIRA with success
        self.logger.info(f"Updating JIRA ticket {ticket_id}")
        
        comment = (
            f"✅ Fixed in PR: {pr_url}\n\n"
            f"A fix has been implemented and all tests are passing.\n"
            f"Please review the pull request and merge if appropriate.\n\n"
            f"Fix generated on attempt {attempt}."
        )
        
        self.jira_client.add_comment(ticket_id, comment)
        self.jira_client.update_ticket(ticket_id, "In Review", comment)
        
        result["jira_updated"] = True
        result["pr_created"] = True
        result["pr_url"] = pr_url
        result["comments_added"].append(comment)
        result["ticket_status"] = "In Review"
        
        return result
        
    def _handle_failed_fix(
        self, 
        ticket_id: str, 
        patch_data: Dict[str, Any], 
        test_results: Dict[str, Any],
        task_plan: Dict[str, Any],
        attempt: int,
        max_retries: int
    ) -> Dict[str, Any]:
        """Handle failed fix based on retry status"""
        self.logger.info(f"Handling failed fix for ticket {ticket_id}, attempt {attempt}/{max_retries}")
        
        result = {
            "jira_updated": False,
            "pr_created": False,
            "pr_url": None,
            "comments_added": [],
            "ticket_status": "unknown"
        }
        
        # Check if we've reached max retries
        if attempt >= max_retries:
            # Max retries reached - escalate
            self.logger.info(f"Max retries ({max_retries}) reached, escalating")
            
            comment = (
                f"⚠️ Could not fix this ticket automatically after {attempt} attempts. "
                f"Escalating to human reviewer.\n\n"
                f"Latest error: {test_results.get('error_message', 'Unknown error')}"
            )
            
            self.jira_client.add_comment(ticket_id, comment)
            self.jira_client.update_ticket(ticket_id, "Needs Review", comment)
            
            result["jira_updated"] = True
            result["comments_added"].append(comment)
            result["ticket_status"] = "Needs Review"
            
        else:
            # More retries available - update with current status
            self.logger.info(f"Attempt {attempt}/{max_retries} failed, more retries available")
            
            comment = (
                f"❌ Fix attempt {attempt}/{max_retries} failed.\n\n"
                f"Error: {test_results.get('error_message', 'Unknown error')}\n\n"
                f"Retrying with a different approach..."
            )
            
            self.jira_client.add_comment(ticket_id, comment)
            
            result["jira_updated"] = True
            result["comments_added"].append(comment)
            result["ticket_status"] = "In Progress"
            
        return result
