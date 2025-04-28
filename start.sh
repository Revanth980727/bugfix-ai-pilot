
#!/bin/bash
echo "Starting BugFix AI system..."

# Create necessary directories if they don't exist
mkdir -p logs
mkdir -p code_repo

# Start the containers in detached mode
docker-compose up -d

echo "System started! Frontend available at http://localhost:3000"
