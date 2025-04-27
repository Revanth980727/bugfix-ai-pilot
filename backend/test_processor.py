
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
from log_utils import log_action

logger = logging.getLogger("test-processor")

def analyze_test_failure(test_results: List[Dict[str, Any]]) -> Tuple[str, bool]:
    """Analyze test failures to determine if they are flaky or hard failures"""
    failing_tests = [t for t in test_results if t["status"] == "fail"]
    
    # Check for potential flaky tests (timeouts, race conditions, etc)
    flaky_indicators = ["timeout", "race condition", "async", "concurrent"]
    flaky_count = sum(1 for test in failing_tests 
                     if any(ind in test.get("errorMessage", "").lower() 
                           for ind in flaky_indicators))
    
    is_flaky = flaky_count > 0 and flaky_count == len(failing_tests)
    failure_type = "flaky" if is_flaky else "hard"
    
    return failure_type, is_flaky

def process_qa_results(ticket_id: str, developer_response: Dict[str, Any], qa_response: Dict[str, Any]) -> bool:
    """Process QA test results and determine if tests passed"""
    # Log QA results
    ticket_log_dir = f"logs/{ticket_id}"
    
    if not qa_response:
        log_action(ticket_id, "qa", "error", {"message": "QA testing failed - no response"})
        return False
        
    # Log the complete QA response
    with open(f"{ticket_log_dir}/qa_output.json", 'w') as f:
        json.dump(qa_response, f, indent=2)
    
    # Get test pass status
    qa_passed = qa_response["passed"]
    
    # If failed, analyze the failure type
    if not qa_passed:
        failure_type, is_flaky = analyze_test_failure(qa_response["test_results"])
        log_action(ticket_id, "qa", "test_failure", {
            "failure_type": failure_type,
            "is_flaky": is_flaky,
            "test_results": qa_response["test_results"]
        })
    
    # Log test statistics
    passed_tests = sum(1 for test in qa_response["test_results"] if test["status"] == "pass")
    total_tests = len(qa_response["test_results"])
    
    log_action(ticket_id, "qa", "test_summary", {
        "passed": passed_tests,
        "total": total_tests,
        "success_rate": f"{(passed_tests/total_tests)*100:.1f}%"
    })
    
    return qa_passed

