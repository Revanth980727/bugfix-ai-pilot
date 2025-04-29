
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p /app/logs
RUN mkdir -p /app/code_repo

# Set up environment variables
ENV PYTHONPATH=/app

# Run the orchestrator with the correct Python module path
CMD ["python", "-m", "orchestrator.start_orchestrator"]
