
#!/bin/bash
echo "Stopping BugFix AI system..."

# Stop and remove containers, networks, and volumes
docker-compose down

echo "System stopped!"
