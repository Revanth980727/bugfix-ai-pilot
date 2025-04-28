
#!/bin/bash
echo "Starting BugFix AI system..."

# Create necessary directories if they don't exist
mkdir -p logs
mkdir -p code_repo

# Check if .env file exists
if [ ! -f .env ]; then
  echo "Error: .env file not found!"
  echo "Please create an .env file based on .env.example before starting the system."
  exit 1
fi

# Start the containers in detached mode
docker-compose up -d

# Check if services started successfully
if [ $? -eq 0 ]; then
  echo "System started successfully! Frontend available at http://localhost:3000"
  echo "To view logs, run: ./logs.sh"
  echo "To stop the system, run: ./stop.sh"
else
  echo "Error starting the system. Please check docker-compose logs for details."
fi
