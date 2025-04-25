
# BugFix AI Pilot

An autonomous AI tool that fixes bugs in your codebase by analyzing JIRA tickets and generating code fixes.

## Architecture

BugFix AI Pilot consists of four specialized AI agents:

1. **Planner Agent**: Analyzes JIRA tickets and identifies affected code areas
2. **Developer Agent**: Generates code fixes using GPT-4
3. **QA Agent**: Runs tests to validate the fixes
4. **Communicator Agent**: Updates JIRA tickets and creates GitHub PRs

## Features

- Runs entirely locally via Docker Compose
- Connects to JIRA Cloud or Server
- Uses GPT-4 via OpenAI API
- Creates GitHub pull requests with fixes
- Retries failed fixes up to 4 times
- Escalates to human review when necessary

## Setup Instructions

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/bugfix-ai-pilot.git
   cd bugfix-ai-pilot
   ```

2. Create a `.env` file with your API credentials:
   ```
   OPENAI_API_KEY=your_openai_key_here
   JIRA_API_TOKEN=your_jira_api_token
   JIRA_USER=your_jira_email
   JIRA_URL=https://your-company.atlassian.net
   GITHUB_TOKEN=your_github_personal_access_token
   ```

3. Start the containers:
   ```
   docker-compose up -d
   ```

4. Access the dashboard at http://localhost:3000

## Development

### Frontend

The frontend is built with React and can be run separately for development:

```
cd frontend
npm install
npm run dev
```

### Backend

The backend and agent services are built with Python and can be run separately:

```
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Extending the System

To add support for additional testing frameworks or version control systems, check the extension guides in the documentation.

## License

MIT
