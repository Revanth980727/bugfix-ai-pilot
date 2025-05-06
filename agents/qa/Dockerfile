
FROM python:3.10-slim

WORKDIR /app

# Install git and other essential tools
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent code to the correct location
COPY ./qa/agent.py /app/
COPY ./utils /app/utils/

# Ensure the mount point exists with proper permissions
RUN mkdir -p /app/code_repo && chmod 777 /app/code_repo
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Make sure uvicorn and pytest are in the PATH
ENV PATH="/usr/local/bin:${PATH}"

# Verify pytest installation
RUN python -c "import pytest; print(f'pytest version: {pytest.__version__}')"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8003"]
