
#!/bin/bash
echo "Starting BugFix AI system..."

# Create necessary directories if they don't exist
mkdir -p logs
mkdir -p code_repo

# Check if .env file exists at the root level
if [ ! -f ./.env ]; then
  echo "Error: .env file not found in the root directory!"
  echo "Please create an .env file based on .env.example before starting the system."
  exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker and try again."
  exit 1
fi

# Start the containers in detached mode
echo "Starting Docker containers..."
docker-compose down  # Stop any existing containers first
docker-compose up -d

# Check if services started successfully
if [ $? -eq 0 ]; then
  echo "System started successfully! Frontend available at http://localhost:3000"
  echo "To view logs, run: ./logs.sh"
  echo "To stop the system, run: ./stop.sh"
else
  echo "Error starting the system."
  echo "Running docker-compose logs to help diagnose the issue:"
  docker-compose logs
  echo "For more detailed logs of a specific service, run: docker-compose logs SERVICE_NAME"
  echo "For example: docker-compose logs backend"
  echo "To stop the system, run: ./stop.sh"
fi
