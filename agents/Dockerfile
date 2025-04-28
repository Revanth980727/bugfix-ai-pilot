
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY . /app/agents/

# Create necessary directories
RUN mkdir -p /app/logs
RUN mkdir -p /mnt/codebase

# Set up environment variables
ENV PYTHONPATH=/app

# Set default command
CMD ["python", "-m", "agents.agent_controller"]
