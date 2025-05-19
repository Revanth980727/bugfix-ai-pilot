
FROM python:3.10-slim

WORKDIR /app

# Install git and other essential tools
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent code and github utilities
COPY ./communicator/agent.py /app/
COPY ./utils /app/utils/

# Create necessary directories with proper permissions
RUN mkdir -p /app/utils
RUN mkdir -p /app/code_repo && chmod 777 /app/code_repo
RUN mkdir -p /app/logs && chmod 777 /app/logs
RUN mkdir -p /app/github_service && chmod 777 /app/github_service

# Add required packages explicitly with error handling
RUN pip install --no-cache-dir PyGithub jira unidiff && \
    echo "Verifying imports..." && \
    python -c "import sys; print('Python path:', sys.path); import github; print('github imported'); import jira; print('jira imported'); import unidiff; print('unidiff imported'); print('All required modules can be imported')"

# Make sure uvicorn is in the PATH
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONPATH="/app:/app/github_service:${PYTHONPATH}"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8004"]
