
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

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the application:
   ```bash
   npm run dev
   ```

4. Open http://localhost:3000 in your browser

5. Enter your API credentials in the settings form
   - GitHub personal access token
   - JIRA API token
   - JIRA user email
   - JIRA domain URL

Your credentials will be stored securely in your browser's local storage.

## Development

### Frontend (React + TypeScript)

```bash
npm install
npm run dev
```

## Security Notes

- API credentials are stored in your browser's local storage
- Never commit API keys or tokens to the repository
- Clear your browser's local storage to remove stored credentials

## Troubleshooting

If you encounter issues:
1. Verify your API credentials are correct
2. Check that your GitHub token has the required permissions
3. Ensure your JIRA domain URL is correct and accessible
4. Clear browser storage and re-enter credentials if needed

## License

MIT
