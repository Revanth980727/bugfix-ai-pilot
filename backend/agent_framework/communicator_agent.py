
import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("communicator-agent")

class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    SUCCESS = "success"
    ERROR = "error"
    ESCALATED = "escalated"

class CommunicatorAgent:
    """
    Agent responsible for communicating fix results to external systems:
    - Updates JIRA tickets with progress, comments and status
    - Creates branches and pull requests in GitHub
    - Validates patches before application
    """
    
    def __init__(self):
        """Initialize the Communicator Agent with necessary clients"""
        self.status = AgentStatus.IDLE
        
        # Initialize JIRA client if credentials are available
        try:
            from agents.utils.jira_client import JiraClient
            self.jira_client = JiraClient()
            logger.info("JIRA client initialized successfully")
        except ImportError:
            logger.warning("JIRA client could not be imported - will mock JIRA interactions")
            self.jira_client = self._create_mock_jira_client()
        except Exception as e:
            logger.error(f"Error initializing JIRA client: {str(e)}")
            self.jira_client = self._create_mock_jira_client()
            
        # Initialize GitHub service if available
        try:
            from backend.github_service.github_service import GitHubService
            self.github_service = GitHubService()
            
            # Check if config is valid (not using placeholders)
            from backend.github_service.config import verify_config
            if verify_config():
                logger.info("GitHub service initialized successfully with valid configuration")
            else:
                logger.error("GitHub service initialized, but configuration is invalid")
                raise ValueError("Invalid GitHub configuration - using placeholders")
        except ImportError as e:
            logger.warning(f"GitHub service could not be imported - will mock GitHub interactions: {e}")
            self.github_service = self._create_mock_github_service()
        except Exception as e:
            logger.error(f"Error initializing GitHub service: {str(e)}")
            self.github_service = self._create_mock_github_service()
            
        # Initialize patch validator
        try:
            from backend.github_service.patch_validator import PatchValidator
            self.patch_validator = PatchValidator()
            self.patch_validator.set_github_client(self.github_service)
            logger.info("Patch validator initialized successfully")
        except ImportError:
            logger.warning("Patch validator could not be imported - will skip validation")
            self.patch_validator = None
        except Exception as e:
            logger.error(f"Error initializing patch validator: {str(e)}")
            self.patch_validator = None
            
        # Check test mode flag
        self.test_mode = os.environ.get("TEST_MODE", "False").lower() == "true"
        if self.test_mode:
            logger.warning("Running in TEST_MODE - using mock implementations")

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the communicator agent tasks based on input
        
        Args:
            input_data: Dictionary with communicator input data
                Required fields:
                - ticket_id: The JIRA ticket ID
                
                Optional fields:
                - test_passed: Boolean indicating if QA tests passed 
                - github_pr_url: Existing PR URL if available
                - patches: List of patch details 
                - retry_count: Current retry attempt number
                - max_retries: Maximum allowed retries
                - confidence_score: Confidence score for the fix
                - early_escalation: Flag indicating early escalation
                - escalation_reason: Reason for early escalation
                
        Returns:
            Dictionary with results of communication tasks
        """
        self.status = AgentStatus.WORKING
        
        ticket_id = input_data.get("ticket_id")
        if not ticket_id:
            logger.error("No ticket ID provided")
            self.status = AgentStatus.ERROR
            return {"error": "No ticket ID provided"}
        
        logger.info(f"Processing communication tasks for ticket {ticket_id}")
        
        # Extract common fields
        retry_count = input_data.get("retry_count", 0)
        max_retries = input_data.get("max_retries", 4)
        confidence_score = input_data.get("confidence_score")
        early_escalation = input_data.get("early_escalation", False)
        escalation_reason = input_data.get("escalation_reason", "Unknown reason")
        
        # Initialize result
        result = {
            "ticket_id": ticket_id,
            "communications_success": False,
            "jira_updated": False,
            "github_updated": False,
            "github_pr_url": None,
            "timestamp": self._get_timestamp(),
            "retry_count": retry_count,
            "max_retries": max_retries
        }
        
        # Track updates for the UI
        updates = []
        
        try:
            # Case 1: Handle early escalation if flagged
            if early_escalation:
                logger.info(f"Processing early escalation for ticket {ticket_id}")
                updates.append(self._create_update(
                    f"Early escalation: {escalation_reason}",
                    "system"
                ))
                
                # Add JIRA escalation comment and update status
                jira_comment = f"⚠️ Early Escalation: {escalation_reason}"
                if confidence_score is not None:
                    jira_comment += f" (Developer confidence: {confidence_score}%)"
                
                updates.append(self._create_update(
                    f"Updating JIRA ticket {ticket_id} with escalation",
                    "jira"
                ))
                
                if await self._update_jira(ticket_id, "Needs Review", jira_comment):
                    result["jira_updated"] = True
                
                self.status = AgentStatus.ESCALATED
                result.update({
                    "escalated": True,
                    "early_escalation": True,
                    "escalation_reason": escalation_reason,
                    "communications_success": True,
                })
                
                # Add updates to result
                result["updates"] = updates
                return result
            
            # Case 2: Process PR if tests passed
            test_passed = self._determine_test_success(input_data)
            
            # If tests passed, create/update PR
            if test_passed:
                logger.info(f"Tests passed for ticket {ticket_id}, handling PR")
                
                # Handle patch validation if patches are provided
                patches = input_data.get("patches", [])
                if patches and self.patch_validator:
                    validation_results = await self._validate_patches(patches)
                    updates.append(self._create_update(
                        f"Patch validation: {'PASSED' if validation_results['isValid'] else 'FAILED'}",
                        "system"
                    ))
                    
                    # Add validation results to the return object
                    result["patch_valid"] = validation_results["isValid"]
                    if not validation_results["isValid"]:
                        result["rejection_reason"] = validation_results["rejectionReason"]
                    result["validation_metrics"] = validation_results["validationMetrics"]
                    
                    # Adjust confidence score based on validation
                    if confidence_score is not None and "confidence_adjustment" in validation_results:
                        confidence_score += validation_results["confidence_adjustment"]
                        confidence_score = max(0, min(100, confidence_score))  # Clamp between 0-100
                        result["confidence_score"] = confidence_score
                    
                    # If patch validation fails and we have details, early return
                    if not validation_results["isValid"]:
                        updates.append(self._create_update(
                            f"Invalid patch detected, cannot create PR: {validation_results['rejectionReason']}",
                            "system"
                        ))
                        
                        # Update JIRA with validation failure
                        jira_comment = f"❌ Patch validation failed: {validation_results['rejectionReason']}"
                        await self._update_jira(ticket_id, "In Progress", jira_comment)
                        
                        # Set result and early return
                        self.status = AgentStatus.ERROR
                        result["updates"] = updates
                        result["communications_success"] = True  # Technically the communication worked
                        return result
                
                # Create or update GitHub PR
                pr_result = await self._handle_github_pr(ticket_id, input_data)
                
                if pr_result["success"]:
                    result["github_updated"] = True
                    result["github_pr_url"] = pr_result["pr_url"]
                    
                    # Add PR update
                    updates.append(self._create_update(
                        f"Created pull request: {pr_result['pr_url']}",
                        "github"
                    ))
                    
                    # Update JIRA with PR info
                    jira_comment = f"✅ Fix implemented successfully!\n\n"
                    jira_comment += f"Pull Request: {pr_result['pr_url']}"
                    
                    updates.append(self._create_update(
                        f"Updating JIRA ticket with PR information",
                        "jira"
                    ))
                    
                    if await self._update_jira(ticket_id, "In Review", jira_comment):
                        result["jira_updated"] = True
                    
                    self.status = AgentStatus.SUCCESS
                else:
                    updates.append(self._create_update(
                        f"Failed to create pull request: {pr_result['error']}",
                        "github" 
                    ))
                    self.status = AgentStatus.ERROR
            else:
                # Case 3: Handle failed tests
                logger.info(f"Tests failed for ticket {ticket_id}, updating status")
                
                # Check if this is the final retry
                final_retry = retry_count >= max_retries
                
                if final_retry:
                    # Max retries reached - update to escalation
                    updates.append(self._create_update(
                        f"Maximum retries ({max_retries}) reached, escalating",
                        "system"
                    ))
                    
                    # Update JIRA with escalation
                    jira_comment = f"⚠️ Maximum retries reached ({max_retries}). Escalating to human developer."
                    updates.append(self._create_update(
                        "Updating JIRA with escalation status",
                        "jira"
                    ))
                    
                    if await self._update_jira(ticket_id, "Needs Review", jira_comment):
                        result["jira_updated"] = True
                    
                    self.status = AgentStatus.ESCALATED
                    result["escalated"] = True
                else:
                    # More retries available - update with retry info
                    updates.append(self._create_update(
                        f"Test failed on attempt {retry_count}/{max_retries}, will retry",
                        "system"
                    ))
                    
                    # Update JIRA with retry info
                    jira_comment = f"❌ Fix attempt {retry_count}/{max_retries} failed. Attempting another approach."
                    updates.append(self._create_update(
                        "Updating JIRA with retry information",
                        "jira"
                    ))
                    
                    if await self._update_jira(ticket_id, "In Progress", jira_comment):
                        result["jira_updated"] = True
                    
            # Success - set communications success flag
            result["communications_success"] = True
            
        except Exception as e:
            logger.error(f"Error in communicator agent: {str(e)}")
            self.status = AgentStatus.ERROR
            updates.append(self._create_update(
                f"Error: {str(e)}",
                "system"
            ))
            result["error"] = str(e)
        
        # Add all updates to the result
        result["updates"] = updates
        
        logger.info(f"Completed communication tasks for ticket {ticket_id}")
        return result
    
    def _determine_test_success(self, input_data: Dict[str, Any]) -> bool:
        """
        Helper method to determine if tests passed by checking multiple possible field names
        
        Args:
            input_data: The input data dictionary
            
        Returns:
            Boolean indicating whether tests passed
        """
        # Check all possible fields that might indicate test success
        # This handles different field names that might be used by different agents
        if input_data.get("test_passed") is True:
            return True
        if input_data.get("passed") is True:
            return True
        if input_data.get("success") is True:
            return True
        if input_data.get("tests_passed") is True:
            return True
        
        # If none of the positive indicators are present, check for explicit failure flags
        if input_data.get("test_passed") is False:
            return False
        if input_data.get("passed") is False:
            return False
        if input_data.get("success") is False:
            return False
        if input_data.get("tests_passed") is False:
            return False
        
        # Default to assuming tests failed if we can't determine otherwise
        # This is conservative but safer than assuming success
        return False
    
    async def _validate_patches(self, patches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate patches for common issues
        
        Args:
            patches: List of patch objects with file_path and diff
            
        Returns:
            Dictionary with validation results
        """
        logger.info(f"Validating {len(patches)} patches")
        
        # Initialize validation metrics
        validation_metrics = {
            "totalPatches": len(patches),
            "validPatches": 0,
            "rejectedPatches": 0,
            "rejectionReasons": {}
        }
        
        file_checksums = {}
        all_valid = True
        rejection_reason = None
        confidence_adjustment = 0
        
        # Process each patch
        for patch in patches:
            file_path = patch.get("file_path", "")
            diff = patch.get("diff", "")
            
            # Skip empty patches
            if not file_path or not diff:
                continue
                
            # Generate simple checksum for the file
            import hashlib
            checksum = hashlib.md5(diff.encode()).hexdigest()
            file_checksums[file_path] = checksum
            
            # Validate file path exists
            if self.patch_validator and not self.patch_validator._is_valid_file_path(file_path):
                all_valid = False
                rejection_reason = f"Invalid file path: {file_path}"
                validation_metrics["rejectedPatches"] += 1
                
                reason_key = "file_path_invalid"
                validation_metrics["rejectionReasons"][reason_key] = \
                    validation_metrics["rejectionReasons"].get(reason_key, 0) + 1
                
                confidence_adjustment -= 10  # Penalty for invalid file path
                continue
            
            # Validate diff syntax
            if self.patch_validator and not self.patch_validator._is_valid_diff_syntax(diff):
                all_valid = False
                rejection_reason = "Invalid diff syntax"
                validation_metrics["rejectedPatches"] += 1
                
                reason_key = "diff_syntax_invalid"
                validation_metrics["rejectionReasons"][reason_key] = \
                    validation_metrics["rejectionReasons"].get(reason_key, 0) + 1
                
                confidence_adjustment -= 15  # Larger penalty for syntax issues
                continue
            
            # Check for placeholders
            if self.patch_validator:
                placeholders = self.patch_validator._check_for_placeholders(file_path, diff)
                if placeholders:
                    all_valid = False
                    rejection_reason = f"Contains placeholder: {placeholders[0]}"
                    validation_metrics["rejectedPatches"] += 1
                    
                    reason_key = "contains_placeholders"
                    validation_metrics["rejectionReasons"][reason_key] = \
                        validation_metrics["rejectionReasons"].get(reason_key, 0) + 1
                    
                    confidence_adjustment -= 20  # Major penalty for placeholders
                    continue
            
            # If we got here, the patch is valid
            validation_metrics["validPatches"] += 1
            confidence_adjustment += 5  # Small boost for each valid patch
        
        # Return validation results
        result = {
            "isValid": all_valid,
            "rejectionReason": rejection_reason,
            "validationMetrics": validation_metrics,
            "fileChecksums": file_checksums,
            "confidence_adjustment": confidence_adjustment
        }
        
        return result
    
    async def _handle_github_pr(self, ticket_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle GitHub PR creation or updating
        
        This method supports multiple patch formats:
        1. List of patches with file_path and diff: input_data.get("patches", [])
        2. Single patch content and list of files: input_data.get("patch_content") & input_data.get("patched_files", [])
        3. Developer result object: input_data.get("developer_result", {})
        
        Args:
            ticket_id: The JIRA ticket ID
            input_data: The input data dictionary
            
        Returns:
            Dictionary with PR handling results
        """
        logger.info(f"Handling GitHub PR for ticket {ticket_id}")
        
        result = {
            "success": False,
            "pr_url": None,
            "error": None
        }
        
        # 1. Check if PR URL is already provided
        pr_url = input_data.get("github_pr_url")
        if pr_url:
            logger.info(f"Using provided PR URL: {pr_url}")
            result["success"] = True
            result["pr_url"] = pr_url
            return result
        
        # 2. Extract patch data from various possible formats
        # Check for the patches list format first
        patches = input_data.get("patches", [])
        patch_content = input_data.get("patch_content", "")
        patched_files = input_data.get("patched_files", [])
        
        # Log the patch data format for debugging
        logger.info(f"Patch data formats - patches list: {bool(patches) and len(patches) > 0}, "
                   f"patch_content: {bool(patch_content) and len(patch_content.strip()) > 0}, "
                   f"patched_files: {len(patched_files) if patched_files else 0}")
        
        if patches:
            logger.debug(f"Found {len(patches)} patches")
            for i, patch in enumerate(patches[:2]):  # Log first few patches
                logger.debug(f"Patch {i}: file={patch.get('file_path', 'unknown')}, "
                           f"diff_length={len(patch.get('diff', ''))}")
        
        if patch_content:
            logger.debug(f"Patch content length: {len(patch_content)}")
            logger.debug(f"First 100 chars of patch: {patch_content[:100]}")
            
        if patched_files:
            logger.debug(f"Patched files: {patched_files}")
        
        # If we have a developer result, try to extract from there as well
        developer_result = input_data.get("developer_result", {})
        if developer_result and isinstance(developer_result, dict):
            # This might override existing values if both are present
            if not patches:
                developer_patches = developer_result.get("patches", [])
                if developer_patches:
                    logger.info(f"Extracted {len(developer_patches)} patches from developer_result")
                    patches = developer_patches
            
            if not patch_content:
                developer_patch_content = developer_result.get("patch_content", "")
                if developer_patch_content and len(developer_patch_content.strip()) > 0:
                    logger.info(f"Extracted patch_content from developer_result "
                              f"(length: {len(developer_patch_content)})")
                    patch_content = developer_patch_content
            
            if not patched_files:
                developer_patched_files = developer_result.get("patched_files", [])
                if developer_patched_files and len(developer_patched_files) > 0:
                    logger.info(f"Extracted {len(developer_patched_files)} patched_files from developer_result")
                    patched_files = developer_patched_files
        
        # Convert patches list to patch_content and patched_files if needed
        if patches and isinstance(patches, list) and len(patches) > 0 and (not patch_content or not patched_files):
            file_changes = []
            extracted_file_paths = []
            
            for patch in patches:
                if not isinstance(patch, dict):
                    continue
                    
                file_path = patch.get("file_path", "")
                diff = patch.get("diff", "")
                
                if file_path and diff:
                    file_changes.append({
                        "filename": file_path,
                        "content": diff
                    })
                    extracted_file_paths.append(file_path)
            
            # If we successfully extracted patches, use those instead
            if file_changes:
                logger.info(f"Extracted {len(file_changes)} file changes from patches list")
                if not patched_files or len(patched_files) == 0:
                    patched_files = extracted_file_paths
                    logger.info(f"Created patched_files list with {len(patched_files)} entries")
        
        # Check if we have any valid patch data after all extraction attempts
        has_patches = False
        
        # Check patches list
        if patches and isinstance(patches, list) and len(patches) > 0:
            valid_patches = [p for p in patches if isinstance(p, dict) and 
                            p.get("file_path") and p.get("diff")]
            if valid_patches:
                has_patches = True
                logger.info(f"Found {len(valid_patches)} valid patches in patch list")
        
        # Check patch_content + patched_files combination
        if (patch_content and isinstance(patch_content, str) and len(patch_content.strip()) > 0 and
            patched_files and isinstance(patched_files, list) and len(patched_files) > 0):
            has_patches = True
            logger.info(f"Found valid patch_content ({len(patch_content)} chars) and "
                       f"patched_files ({len(patched_files)} files)")
            
        if not has_patches:
            logger.error("No valid patches provided after checking all possible formats")
            result["error"] = "No valid patches provided"
            
            # Log the specific validation issues
            if not patches and not patch_content:
                logger.error("Both patches list and patch_content are empty")
            elif patches and (not isinstance(patches, list) or len(patches) == 0):
                logger.error(f"Patches is not a valid list or is empty: {type(patches)}")
            elif patch_content and (not isinstance(patch_content, str) or len(patch_content.strip()) == 0):
                logger.error("patch_content is not a valid string or is empty/whitespace")
            elif not patched_files:
                logger.error("patched_files is empty")
            elif not isinstance(patched_files, list) or len(patched_files) == 0:
                logger.error(f"patched_files is not a valid list or is empty: {type(patched_files)}")
                
            return result
        
        # If we're in test mode, warn that we'll use mocked PR creation
        if self.test_mode:
            logger.warning("TEST_MODE enabled - using mock PR creation")
            # In test mode, create a placeholder PR URL
            import datetime
            pr_number = int(datetime.datetime.now().timestamp()) % 1000
            mock_pr_url = f"https://github.com/test-org/test-repo/pull/{pr_number}"
            result["success"] = True
            result["pr_url"] = mock_pr_url
            logger.info(f"Created mock PR URL for test mode: {mock_pr_url}")
            return result
        
        # 3. Try to find existing PR for this branch
        branch_name = f"fix/{ticket_id}"
        
        # Check if PR already exists for this branch
        existing_pr = self.github_service.find_pr_for_branch(branch_name)
        if existing_pr:
            logger.info(f"Found existing PR for branch {branch_name}: {existing_pr.get('url')}")
            result["success"] = True
            result["pr_url"] = existing_pr.get("url")
            return result
            
        # 4. Create branch and PR
        # Create a branch for the fix
        branch_created, actual_branch_name = self.github_service.create_fix_branch(ticket_id)
        if not branch_created:
            logger.error(f"Failed to create branch {branch_name}")
            result["error"] = "Failed to create branch"
            return result
        
        # Use the actual branch name from the service
        branch_name = actual_branch_name or branch_name
        logger.info(f"Branch created: {branch_name}")
        
        # Prepare file changes for commit
        file_changes = []
        
        # Handle the two different formats for patches
        if patches and isinstance(patches, list) and len(patches) > 0:
            # Format 1: List of patches with file_path and diff
            for patch in patches:
                if isinstance(patch, dict):
                    file_path = patch.get("file_path", "")
                    diff = patch.get("diff", "")
                    
                    if file_path and diff:
                        file_changes.append({
                            "filename": file_path,
                            "content": diff
                        })
        elif patch_content and patched_files:
            # Format 2: Single patch content with list of files
            # In this format, we need to distribute the patch content across files
            for file_path in patched_files:
                file_changes.append({
                    "filename": file_path,
                    "content": patch_content
                })
        
        # Commit the changes
        commit_message = f"Fix {ticket_id}: Automated bug fix"
        if "commit_message" in input_data:
            commit_message = input_data["commit_message"]
        elif developer_result and "commit_message" in developer_result:
            commit_message = developer_result["commit_message"]
            
        # Ensure commit message starts with ticket ID
        if not commit_message.startswith(f"Fix {ticket_id}"):
            commit_message = f"Fix {ticket_id}: {commit_message}"
            
        logger.info(f"Committing {len(file_changes)} file changes to branch {branch_name}")
        commit_success, commit_details = self.github_service.commit_bug_fix(
            branch_name, 
            file_changes,
            ticket_id,
            commit_message
        )
        
        if not commit_success:
            logger.error(f"Failed to commit changes: {commit_details}")
            result["error"] = "Failed to commit changes"
            return result
            
        # Create pull request
        pr_title = f"Fix {ticket_id}"
        pr_body = f"Automated bug fix for issue {ticket_id}"
        
        logger.info(f"Creating pull request for branch {branch_name}")
        pr_result = self.github_service.create_fix_pr(
            branch_name,
            ticket_id,
            pr_title,
            pr_body
        )
        
        if not pr_result:
            logger.error("Failed to create pull request - PR result is None or empty")
            result["error"] = "Failed to create pull request"
            return result
        
        # Handle different return types from github_service
        if isinstance(pr_result, dict):
            pr_url = pr_result.get('url')
            logger.info(f"PR created: {pr_url}")
            
            # Validate PR URL - shouldn't contain placeholders
            if pr_url and not ("org/repo" in pr_url or "test-org/test-repo" in pr_url):
                result["success"] = True
                result["pr_url"] = pr_url
            else:
                logger.error(f"Created PR URL contains placeholder values: {pr_url}")
                result["error"] = "PR URL contains placeholder values"
                result["pr_url"] = None
        elif isinstance(pr_result, tuple) and len(pr_result) > 0:
            pr_url = pr_result[0]
            logger.info(f"PR created: {pr_url}")
            
            # Validate PR URL
            if pr_url and not ("org/repo" in pr_url or "test-org/test-repo" in pr_url):
                result["success"] = True
                result["pr_url"] = pr_url
            else:
                logger.error(f"Created PR URL contains placeholder values: {pr_url}")
                result["error"] = "PR URL contains placeholder values"
                result["pr_url"] = None
        elif isinstance(pr_result, str):
            pr_url = pr_result
            logger.info(f"PR created: {pr_url}")
            
            # Validate PR URL
            if pr_url and not ("org/repo" in pr_url or "test-org/test-repo" in pr_url):
                result["success"] = True
                result["pr_url"] = pr_url
            else:
                logger.error(f"Created PR URL contains placeholder values: {pr_url}")
                result["error"] = "PR URL contains placeholder values"
                result["pr_url"] = None
        else:
            logger.error(f"Unexpected PR result type: {type(pr_result)}")
            result["error"] = "Unexpected PR result type"
        
        return result
    
    async def _update_jira(self, ticket_id: str, status: str, comment: str) -> bool:
        """Update JIRA ticket with new status and comment"""
        try:
            # Add the comment
            await self.jira_client.add_comment(ticket_id, comment)
            
            # Update the status
            await self.jira_client.update_ticket(ticket_id, status, comment)
            
            return True
        except Exception as e:
            logger.error(f"Error updating JIRA: {str(e)}")
            return False
    
    def _create_update(self, message: str, type_str: str = "system") -> Dict[str, Any]:
        """Create an update message for the UI"""
        import datetime
        
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "message": message,
            "type": type_str
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string"""
        import datetime
        return datetime.datetime.now().isoformat()
        
    def _create_mock_jira_client(self):
        """Create a mock JIRA client for testing"""
        from unittest.mock import AsyncMock, MagicMock
        
        mock_client = MagicMock()
        # Use AsyncMock for async methods
        mock_client.update_ticket = AsyncMock(return_value=True)
        mock_client.add_comment = AsyncMock(return_value=True)
        
        return mock_client
        
    def _create_mock_github_service(self):
        """Create a mock GitHub service for testing"""
        from unittest.mock import MagicMock
        
        mock_service = MagicMock()
        mock_service.create_fix_branch = MagicMock(return_value=(True, "fix/mock-ticket"))
        mock_service.commit_bug_fix = MagicMock(return_value=(True, "Commit successful"))
        mock_service.create_fix_pr = MagicMock(return_value={"url": "https://github.com/test-org/test-repo/pull/123", "number": 123})
        mock_service.find_pr_for_branch = MagicMock(return_value=None)
        
        return mock_service

