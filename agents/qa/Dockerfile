
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

# Create proper directories with permissions
RUN mkdir -p /app/code_repo && chmod 777 /app/code_repo
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Make sure pytest is properly installed and in PATH
RUN pip install pytest --upgrade
RUN python -m pytest --version
ENV PATH="/usr/local/bin:${PATH}"

# Set environment variables
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV TEST_COMMAND="python -m pytest"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8003"]
