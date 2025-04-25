
# BugFix AI Pilot

An autonomous AI tool that fixes bugs in your codebase by analyzing JIRA tickets and generating code fixes.

## Prerequisites

Before running this application, you'll need:

1. A [Supabase](https://supabase.com) account (free tier works)
2. JIRA API credentials (API token and domain)
3. GitHub personal access token
4. OpenAI API key

## Setup Instructions

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/bugfix-ai-pilot.git
   cd bugfix-ai-pilot
   ```

2. Connect to Supabase:
   - Create a new Supabase project
   - Click the green Supabase button in your Lovable project
   - Follow the connection process
   - Store your API credentials in Supabase secrets:
     - OPENAI_API_KEY
     - JIRA_API_TOKEN
     - JIRA_USER
     - JIRA_URL
     - GITHUB_TOKEN

3. Start the application:
   ```bash
   docker-compose up -d
   ```

4. Access the dashboard at http://localhost:3000

## Development

### Frontend (React + TypeScript)

```bash
cd frontend
npm install
npm run dev
```

### Backend (Python + FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Agent Services

Each agent (Planner, Developer, QA, Communicator) runs in its own container:

```bash
docker-compose up planner developer qa communicator
```

## Architecture

The application consists of:

1. Frontend: React + TypeScript dashboard
2. Backend: FastAPI server coordinating agents
3. Agent Services:
   - Planner: Analyzes JIRA tickets
   - Developer: Generates fixes
   - QA: Validates changes
   - Communicator: Updates JIRA/GitHub

## Security Notes

- Never commit API keys or secrets to the repository
- Use Supabase to manage all sensitive credentials
- Enable appropriate access controls in JIRA and GitHub

## Troubleshooting

If you encounter issues:
1. Check Supabase connection status
2. Verify API credentials in Supabase secrets
3. Check Docker container logs
4. Ensure all required ports are available

## License

MIT
