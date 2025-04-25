
# BugFix AI Backend

FastAPI backend service that coordinates the bug fix workflow.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

## API Documentation

Once running, visit http://localhost:8000/docs for the OpenAPI documentation.

The backend service expects API credentials to be passed in the request headers from the frontend application.
