
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
   - `JIRA_TOKEN`: Your JIRA API token
   - `JIRA_USER`: Your JIRA email address
   - `JIRA_URL`: Your JIRA instance URL

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
   # Start the backend
   cd backend
   uvicorn main:app --reload
   
   # In another terminal, start the frontend
   cd frontend
   npm run dev
   ```

5. Open http://localhost:3000 in your browser

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

## License

MIT
