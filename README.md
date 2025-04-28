
# BugFix AI Pilot

An autonomous AI tool that fixes bugs in your codebase by analyzing JIRA tickets and generating code fixes.

## Prerequisites

Before running this application, you'll need:

1. A GitHub personal access token with repo permissions
   - Go to GitHub Settings > Developer Settings > Personal Access Tokens
   - Generate a new token with 'repo' scope

2. JIRA API credentials
   - Go to https://id.atlassian.com/manage-profile/security/api-tokens
   - Create an API token
   - Note your Atlassian account email and JIRA domain URL

3. OpenAI API key
   - Go to https://platform.openai.com/account/api-keys
   - Create a new API key

## Setup Instructions

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/bugfix-ai-pilot.git
   cd bugfix-ai-pilot
   ```

2. Set up your environment variables:
   ```bash
   cd backend
   cp .env.example .env
   ```
   Edit the `.env` file with your API credentials:
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - `GITHUB_REPO_OWNER`: Your GitHub username or organization
   - `GITHUB_REPO_NAME`: Your repository name
   - `JIRA_TOKEN`: Your JIRA API token
   - `JIRA_USER`: Your JIRA email address
   - `JIRA_URL`: Your JIRA instance URL
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `OPENAI_MODEL`: The model to use (default: gpt-4o)

3. Install dependencies:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt
   
   # Frontend
   cd ../
   npm install
   ```

4. Start the application:
   ```bash
   # Using Docker Compose (recommended)
   docker-compose up -d
   
   # Or manually:
   # Start the backend
   cd backend
   uvicorn main:app --reload
   
   # In another terminal, start the frontend
   cd frontend
   npm run dev
   ```

5. Open http://localhost:3000 in your browser

## Architecture

### Agent System

The application uses a multi-agent architecture with four specialized AI agents:

1. **Planner Agent** - Analyzes tickets and identifies affected code areas
2. **Developer Agent** - Generates code fixes based on the planner's analysis
3. **QA Agent** - Validates the fixes by running tests
4. **Communicator Agent** - Updates JIRA tickets and creates GitHub PRs

Each agent runs as a separate microservice and communicates through REST APIs. The main backend coordinates the workflow between agents.

### API Integration Clients

This system includes two API client libraries for interacting with external services:

#### JIRA Client (`agents/utils/jira_client.py`)

Provides functionality to:
- Fetch tickets by ID
- Get open bug tickets
- Add comments to tickets 
- Update ticket status (with transitions)

Usage:
```python
from agents.utils.jira_client import JiraClient

# Initialize the client
jira = JiraClient()

# Get open bug tickets
bug_tickets = jira.get_open_bugs(max_results=10)

# Update a ticket
jira.update_ticket("PROJ-123", "In Progress", "Working on this ticket now")
```

#### GitHub Client (`agents/utils/github_client.py`)

Provides functionality to:
- Get file contents from a repository
- Update files in a repository
- Create branches
- Create pull requests
- Commit patches (code changes)

Usage:
```python
from agents.utils.github_client import GitHubClient

# Initialize the client
github = GitHubClient()

# Create a branch for a bug fix
github.create_branch("fix-PROJ-123")

# Create a PR
pr_url = github.create_pull_request(
    title="Fix for PROJ-123",
    body="This PR fixes the issue described in PROJ-123",
    head_branch="fix-PROJ-123"
)
```

#### OpenAI Client (`agents/utils/openai_client.py`)

Provides functionality to:
- Generate code completions using GPT-4
- Handle API errors and retries
- Manage authentication securely

Usage:
```python
from agents.utils.openai_client import OpenAIClient

# Initialize the client
openai_client = OpenAIClient()

# Generate code completion
completion = openai_client.generate_completion(
    "Generate code to fix the following bug: ..."
)
```

### Directory Structure

```
.
├── agents/
│   ├── planner/       # Analyzes tickets to identify root causes
│   ├── developer/     # Generates code fixes
│   ├── qa/            # Validates fixes with tests
│   ├── communicator/  # Updates JIRA and creates PRs
│   └── utils/
│       ├── jira_client.py    # JIRA API integration
│       ├── github_client.py  # GitHub API integration
│       ├── openai_client.py  # OpenAI API integration
│       └── logger.py         # Logging utilities
├── backend/           # Main backend service
├── src/               # Frontend React application
└── docker-compose.yml # Container orchestration
```

## Development

### Frontend (React + TypeScript)

```bash
npm install
npm run dev
```

### Backend (FastAPI)

```bash
cd backend
uvicorn main:app --reload
```

### Agent Services

Each agent has its own Python/FastAPI service in the `agents/` directory.

```bash
# Run individual agents (development mode)
cd agents/planner
uvicorn agent:app --reload --port 8001

cd agents/developer
uvicorn agent:app --reload --port 8002

cd agents/qa
uvicorn agent:app --reload --port 8003

cd agents/communicator
uvicorn agent:app --reload --port 8004
```

## Security Notes

- Never commit your `.env` file to version control
- Keep your API tokens secure and rotate them regularly
- Store your API keys only in the backend `.env` file

## Troubleshooting

If you encounter issues:
1. Verify your API credentials in the backend `.env` file are correct
2. Check that your GitHub token has the required permissions
3. Ensure your JIRA domain URL is correct and accessible
4. Check the backend logs for detailed error messages
5. Verify agent health with `GET /agents/health` endpoint

## License

MIT
