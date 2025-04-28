
#!/usr/bin/env python3
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.orchestrator import start_orchestrator

if __name__ == "__main__":
    try:
        asyncio.run(start_orchestrator())
    except KeyboardInterrupt:
        print("Orchestrator stopped by user")
