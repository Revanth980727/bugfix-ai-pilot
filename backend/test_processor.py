
import logging
import json
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("test-processor")

def process_qa_results(ticket_id: str, developer_response: Dict[str, Any], qa_response: Dict[str, Any]) -> bool:
    """Process QA test results and determine if tests passed"""
    # Log QA results
    ticket_log_dir = f"logs/{ticket_id}"
    
    if qa_response:
        with open(f"{ticket_log_dir}/qa_output.json", 'w') as f:
            json.dump(qa_response, f, indent=2)
    else:
        # Log error
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "message": "QA testing failed"
        }
        with open(f"{ticket_log_dir}/qa_errors.json", 'a') as f:
            f.write(json.dumps(error_log) + "\n")
            
    if not qa_response:
        return False

    # Get test pass status
    qa_passed = qa_response["passed"]
    
    # Log test statistics
    passed_tests = sum(1 for test in qa_response["test_results"] if test["status"] == "pass")
    total_tests = len(qa_response["test_results"])
    
    logger.info(f"QA results for {ticket_id}: {passed_tests}/{total_tests} tests passed")
    
    return qa_passed

