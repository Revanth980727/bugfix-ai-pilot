
FROM python:3.10-slim

WORKDIR /app

# Install git and other essential tools
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent code to the correct location
COPY ./developer/agent.py /app/
COPY ./utils /app/utils/

# Create necessary directories with proper permissions
RUN mkdir -p /app/code_repo && chmod 777 /app/code_repo
RUN mkdir -p /app/logs && chmod 777 /app/logs
RUN mkdir -p /app/backend && chmod 777 /app/backend

# Install the unidiff package for diff parsing
RUN pip install --no-cache-dir unidiff

# Make sure uvicorn is in the PATH and set proper PYTHONPATH
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONPATH="/app:/app/backend:${PYTHONPATH}"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8002"]
