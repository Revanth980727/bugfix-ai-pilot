
import re
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from .agent_base import Agent

class PlannerAgent(Agent):
    def __init__(self):
        super().__init__(name="PlannerAgent")
        self.output_dir = os.path.join(os.path.dirname(__file__), "planner_outputs")
        os.makedirs(self.output_dir, exist_ok=True)

    def _extract_files(self, text: str) -> List[str]:
        """Extract potential filenames from text using common extensions"""
        file_pattern = r'(?:^|\s)([a-zA-Z0-9_\-./]+\.(?:py|js|tsx?|jsx|css|html))(?:$|\s)'
        return list(set(re.findall(file_pattern, text)))

    def _extract_modules(self, text: str) -> List[str]:
        """Extract potential module names from text"""
        module_pattern = r'(?:^|\s)(?:from\s+|import\s+)([a-zA-Z0-9_\.]+)(?:$|\s)'
        modules = re.findall(module_pattern, text)
        # Also look for React component names (PascalCase)
        component_pattern = r'\b([A-Z][a-zA-Z0-9]+(?:Component|Service|Hook|Utils?|Helper))\b'
        components = re.findall(component_pattern, text)
        return list(set(modules + components))

    def _extract_functions(self, text: str) -> List[str]:
        """Extract potential function or class names from text"""
        # Look for function calls or definitions
        func_pattern = r'\b(?:def\s+|class\s+|function\s+)([a-zA-Z0-9_]+)\b'
        functions = re.findall(func_pattern, text)
        # Look for camelCase method names
        method_pattern = r'\b([a-z][a-zA-Z0-9]+(?:Function|Method|Handler|Callback))\b'
        methods = re.findall(method_pattern, text)
        return list(set(functions + methods))

    def _extract_errors(self, text: str) -> List[str]:
        """Extract potential error messages from text"""
        # Look for typical error patterns
        error_patterns = [
            r'Error:\s+([^\n]+)',
            r'Exception:\s+([^\n]+)',
            r'Traceback[^:]*:\s+([^\n]+)',
            r'Failed[^:]*:\s+([^\n]+)'
        ]
        errors = []
        for pattern in error_patterns:
            errors.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(errors))

    def _generate_summary(self, title: str, description: str, 
                         files: List[str], modules: List[str], 
                         functions: List[str], errors: List[str]) -> str:
        """Generate a concise summary of the analysis"""
        summary_parts = []
        
        if errors:
            summary_parts.append(f"Error(s) identified: {errors[0]}")
        
        if files:
            summary_parts.append(f"Affects {len(files)} file(s)")
            
        if modules:
            summary_parts.append(f"Involves {len(modules)} module(s)")
            
        if functions:
            summary_parts.append(f"Touches {len(functions)} function(s)")
            
        summary = " | ".join(summary_parts) if summary_parts else "No specific technical context identified"
        return f"Bug: {title}. {summary}"

    def _save_output(self, ticket_id: str, output_data: Dict[str, Any]) -> None:
        """Save the analysis output to a JSON file"""
        filename = f"planner_output_{ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(output_data, f, indent=2)
        self.log(f"Analysis output saved to {filepath}")

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ticket and plan approach"""
        self.log("Starting ticket analysis")
        
        ticket_id = input_data.get("ticket_id", "")
        title = input_data.get("title", "")
        description = input_data.get("description", "")
        full_text = f"{title}\n{description}"
        
        try:
            # Extract relevant information
            files = self._extract_files(full_text)
            self.log(f"Found {len(files)} potential affected files")
            
            modules = self._extract_modules(full_text)
            self.log(f"Found {len(modules)} potential affected modules")
            
            functions = self._extract_functions(full_text)
            self.log(f"Found {len(functions)} potential affected functions")
            
            errors = self._extract_errors(full_text)
            self.log(f"Found {len(errors)} potential error patterns")
            
            # Generate analysis output
            output = {
                "ticket_id": ticket_id,
                "affected_files": files,
                "affected_modules": modules,
                "affected_functions": functions,
                "errors_identified": errors,
                "summary": self._generate_summary(title, description, files, modules, functions, errors),
                "timestamp": datetime.now().isoformat()
            }
            
            # Save output for debugging/inspection
            self._save_output(ticket_id, output)
            
            self.log("Analysis completed successfully")
            return output
            
        except Exception as e:
            error_msg = f"Error during ticket analysis: {str(e)}"
            self.log(error_msg)
            return {
                "ticket_id": ticket_id,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }

