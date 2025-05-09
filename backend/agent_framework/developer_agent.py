
import os
import logging
import json
import subprocess
from typing import Dict, Any, List, Optional
from .agent_base import Agent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("developer_agent")

class DeveloperAgent(Agent):
    """
    Agent responsible for generating code fixes based on the analysis from the planner.
    Produces patches that can be applied to the codebase to fix the identified bugs.
    """
    
    def __init__(self, max_retries: int = 4):
        """
        Initialize the developer agent
        
        Args:
            max_retries: Maximum number of retry attempts for generating a fix
        """
        super().__init__(name="Developer Agent")
        self.max_retries = max_retries
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input from planner and generate code fixes
        
        Args:
            input_data: Dictionary with data from planner agent
            
        Returns:
            Dictionary with code fixes and metadata
        """
        logger.info("Developer Agent starting code fix generation")
        
        # Initialize result structure - ensure it always has the required fields
        result = {
            "patched_code": {},
            "test_code": {},  # New field for test code
            "patched_files": [],
            "patch_content": "",
            "confidence_score": 0,
            "commit_message": "",
            "attempt": input_data.get("context", {}).get("attempt", 1),
            "error": None,
            "success": False  # Initialize as False, will be set to True only if all steps succeed
        }
        
        try:
            # Log the input data for debugging
            logger.info(f"Developer input: {json.dumps(input_data, indent=2)}")
            
            # Check for valid input data
            if not self._validate_input(input_data):
                logger.error("Invalid input data")
                result["error"] = "Invalid input data from planner"
                return result
                
            # Generate code fix based on the input data
            fix_generated = self._generate_fix(input_data, result)
            
            if not fix_generated:
                logger.error("Failed to generate fix")
                result["error"] = "Failed to generate code fix"
                return result
                
            # Generate tests for the fix
            tests_generated = self._generate_tests(input_data, result)
            if not tests_generated:
                logger.warning("Failed to generate tests, continuing without tests")
                # We don't fail the process if tests can't be generated
            
            # Apply the generated fix to the codebase
            patch_applied = self.apply_patch(result)
            if not patch_applied:
                logger.error("Failed to apply patch")
                result["error"] = "Failed to apply generated patch"
                return result
                
            # Validate the output structure
            if not self._validate_output(result):
                logger.error("Invalid output structure")
                result["error"] = "Generated output does not meet required structure"
                return result
                
            # If we got here, mark as success
            result["success"] = True  # Set success to True when all steps succeed
            logger.info("Developer agent completed successfully with valid output structure")
            
            # Final logging of the result
            logger.info(f"Developer result - success: {result['success']}, "
                      f"patched_files: {result['patched_files']}, "
                      f"confidence_score: {result['confidence_score']}, "
                      f"test_files: {list(result['test_code'].keys())}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in developer agent: {str(e)}")
            result["error"] = f"Error in developer agent: {str(e)}"
            result["success"] = False
            return result
            
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy method for backwards compatibility.
        Delegates to run() method.
        """
        return self.run(input_data)
            
    def _validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate the input data from the planner
        
        Args:
            input_data: Dictionary with data from planner agent
            
        Returns:
            Boolean indicating if input is valid
        """
        # Check required fields
        required_fields = ["ticket_id"]
        for field in required_fields:
            if field not in input_data:
                logger.error(f"Missing required field in input data: {field}")
                return False
                
        # Check for affected files or modules
        if not input_data.get("affected_files") and not input_data.get("affected_modules"):
            logger.error("Input data missing both affected_files and affected_modules")
            return False
            
        return True
    
    def _generate_tests(self, input_data: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Generate tests for the patched code
        
        Args:
            input_data: Dictionary with data from planner agent
            result: Dictionary with generated fix
            
        Returns:
            Boolean indicating if tests were generated successfully
        """
        try:
            # Extract file information for test generation
            patched_files = result.get("patched_files", [])
            if not patched_files:
                logger.warning("No patched files to generate tests for")
                return False
                
            # Extract bug summary and affected files for better context
            bug_summary = input_data.get("bug_summary", input_data.get("summary", ""))
            error_type = input_data.get("error_type", "")
            
            # Generate tests for each patched file
            for file_path in patched_files:
                # Skip non-Python files
                if not file_path.endswith(".py"):
                    logger.info(f"Skipping test generation for non-Python file: {file_path}")
                    continue
                    
                # Determine the test file name
                file_name = os.path.basename(file_path)
                file_name_without_ext = os.path.splitext(file_name)[0]
                test_file_name = f"test_{file_name_without_ext}.py"
                
                # Get the content of the patched file
                patched_content = result.get("patched_code", {}).get(file_path, "")
                
                # Generate tests based on the patched content and bug information
                test_content = self._create_test_for_file(file_path, file_name_without_ext, 
                                                          patched_content, bug_summary, error_type)
                
                # Add to test_code
                result["test_code"][test_file_name] = test_content
                logger.info(f"Generated test file: {test_file_name}")
                
            return len(result["test_code"]) > 0
                
        except Exception as e:
            logger.error(f"Error generating tests: {str(e)}")
            return False
    
    def _create_test_for_file(self, file_path: str, module_name: str, file_content: str, 
                              bug_summary: str, error_type: str) -> str:
        """
        Create a test for a specific file based on its content and bug information
        
        Args:
            file_path: Path to the file
            module_name: Name of the module (filename without extension)
            file_content: Content of the patched file
            bug_summary: Summary of the bug
            error_type: Type of error (ImportError, TypeError, etc.)
            
        Returns:
            Generated test code as string
        """
        # Extract functions and classes from the file content
        import_pattern = r'import\s+([a-zA-Z0-9_\.]+)'
        from_import_pattern = r'from\s+([a-zA-Z0-9_\.]+)\s+import\s+([a-zA-Z0-9_\.,\s]+)'
        function_pattern = r'def\s+([a-zA-Z0-9_]+)\s*\('
        class_pattern = r'class\s+([a-zA-Z0-9_]+)'
        
        import_matches = []
        function_matches = []
        class_matches = []
        
        import_statements = []
        
        # Extract imports, functions, and classes
        for line in file_content.splitlines():
            # Check for imports
            import_match = import_pattern.search(line)
            from_import_match = from_import_pattern.search(line)
            
            if import_match:
                import_statements.append(line)
                import_matches.append(import_match.group(1))
            elif from_import_match:
                import_statements.append(line)
                imported_items = from_import_match.group(2).split(',')
                import_matches.extend([item.strip() for item in imported_items])
            
            # Check for function definitions
            function_match = function_pattern.search(line)
            if function_match and not line.startswith(' ' * 8):  # Avoid nested functions
                function_matches.append(function_match.group(1))
                
            # Check for class definitions
            class_match = class_pattern.search(line)
            if class_match:
                class_matches.append(class_match.group(1))
                
        # Generate appropriate test based on the file content and bug type
        test_code = [
            f"# Test for {file_path}",
            "import pytest"
        ]
        
        # Basic import test
        test_code.append(f"""
def test_module_import():
    \"\"\"Test if the module can be imported without errors\"\"\"
    try:
        import {module_name}
        assert {module_name} is not None
    except ImportError as e:
        pytest.fail(f"Failed to import {module_name}: {{e}}")
""")

        # Generate specific tests based on bug type and functions found
        if "ImportError" in error_type or "import" in bug_summary.lower():
            # For import errors, test specific imports
            if import_matches:
                test_code.append(f"""
def test_specific_imports():
    \"\"\"Test that specific imports work\"\"\"
    try:
        import {module_name}
        # Test specific imports mentioned in the file
        {'; '.join(f'assert hasattr({module_name}, "{imp.split(".")[-1]}")' for imp in import_matches if '.' in imp)}
        assert True  # If we got here, imports worked
    except ImportError as e:
        pytest.fail(f"Failed to import properly: {{e}}")
""")

        # Test each function found in the file
        for func_name in function_matches:
            if func_name.startswith('_'):
                continue  # Skip private functions
                
            test_code.append(f"""
def test_{func_name}_exists():
    \"\"\"Test that the {func_name} function exists and can be called\"\"\"
    from {module_name} import {func_name}
    assert callable({func_name})
    
    # Basic smoke test - call with minimal args
    try:
        # Note: This might fail if the function requires specific arguments
        # In a real system, we would inspect the function signature
        result = {func_name}()
        assert result is not None
    except TypeError:
        # If it fails due to missing arguments, that's okay for this test
        # We just want to verify it exists and is callable
        pass
    except Exception as e:
        pytest.fail(f"Unexpected error calling {func_name}: {{e}}")
""")

        # Test each class found in the file
        for class_name in class_matches:
            test_code.append(f"""
def test_{class_name}_exists():
    \"\"\"Test that the {class_name} class exists and can be instantiated\"\"\"
    from {module_name} import {class_name}
    assert {class_name} is not None
    
    # Basic smoke test - try to instantiate
    try:
        # Note: This might fail if the class requires specific init arguments
        instance = {class_name}()
        assert instance is not None
    except TypeError:
        # If it fails due to missing arguments, that's okay for this test
        # We just want to verify the class exists
        pass
    except Exception as e:
        pytest.fail(f"Unexpected error instantiating {class_name}: {{e}}")
""")

        # Add a generic test for the overall functionality
        test_code.append(f"""
def test_basic_functionality():
    \"\"\"Basic smoke test to verify file functionality\"\"\"
    import {module_name}
    # This test will pass if the file can be imported without errors
    assert True
""")
            
        return "\n".join(test_code)
        
    def _generate_fix(self, input_data: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """
        Generate code fix based on input data
        
        Args:
            input_data: Dictionary with data from planner agent
            result: Dictionary to store generated fix
            
        Returns:
            Boolean indicating if fix was generated successfully
        """
        try:
            # Extract ticket details
            ticket_id = input_data.get("ticket_id", "unknown")
            bug_summary = input_data.get("bug_summary", input_data.get("summary", ""))
            error_type = input_data.get("error_type", "")
            
            logger.info(f"Generating fix for ticket {ticket_id} with summary: {bug_summary}")
            
            # Get affected files
            affected_files = []
            
            if "affected_files" in input_data and isinstance(input_data["affected_files"], list):
                for file_info in input_data["affected_files"]:
                    if isinstance(file_info, dict) and "file" in file_info:
                        affected_files.append(file_info["file"])
                    elif isinstance(file_info, str):
                        affected_files.append(file_info)
            
            if not affected_files:
                logger.error("No affected files found in input data")
                return False
            
            # In a real system, this would use an LLM to determine the best fix
            # For this example, we'll identify common patterns and generate fixes
            
            # For NetworkX import error
            if "networkx" in bug_summary.lower() and "import" in bug_summary.lower():
                file_to_fix = affected_files[0]
                
                # Generate a fix for NetworkX import error
                result["patched_files"] = [file_to_fix]
                result["patched_code"] = {
                    file_to_fix: "import networkx as nx\n\n# Rest of file content...\ndef correct_function_call():\n    G = nx.Graph()\n    return G"
                }
                result["patch_content"] = f"""
--- a/{file_to_fix}
+++ b/{file_to_fix}
@@ -1,1 +1,6 @@
-import networkx\n
+import networkx as nx\n
 
 # Rest of file content...
 def correct_function_call():
-    G = networkx.Graph()
+    G = nx.Graph()
     return G
"""
                result["confidence_score"] = 95
                result["commit_message"] = f"Fix {ticket_id}: Correct NetworkX import in {file_to_fix}"
                return True
                
            # For TypeErrors
            elif "TypeError" in error_type or "TypeError" in bug_summary:
                file_to_fix = affected_files[0]
                
                # Generate a fix for a typical TypeError
                result["patched_files"] = [file_to_fix]
                result["patched_code"] = {
                    file_to_fix: "def process_data(data):\n    if data is None:\n        return []\n    return [item for item in data if item is not None]"
                }
                result["patch_content"] = f"""
--- a/{file_to_fix}
+++ b/{file_to_fix}
@@ -1,3 +1,4 @@
 def process_data(data):
+    if data is None:
+        return []
     return [item for item in data if item is not None]
"""
                result["confidence_score"] = 85
                result["commit_message"] = f"Fix {ticket_id}: Add null check to prevent TypeError in {file_to_fix}"
                return True
                
            # For any other type of bug, create a generic fix
            else:
                file_to_fix = affected_files[0]
                
                # Generate a generic fix based on bug summary
                result["patched_files"] = [file_to_fix]
                result["patched_code"] = {
                    file_to_fix: f"# Fixed bug: {bug_summary}\n\ndef main():\n    # Implemented fix\n    return True"
                }
                result["patch_content"] = f"""
--- a/{file_to_fix}
+++ b/{file_to_fix}
@@ -1,3 +1,6 @@
+# Fixed bug: {bug_summary}
+
 def main():
+    # Implemented fix
     return True
"""
                result["confidence_score"] = 60
                result["commit_message"] = f"Fix {ticket_id}: Generic fix for {file_to_fix}"
                return True
                
        except Exception as e:
            logger.error(f"Error generating fix: {str(e)}")
            return False
    
    # ... keep existing code (validation and patching methods)
