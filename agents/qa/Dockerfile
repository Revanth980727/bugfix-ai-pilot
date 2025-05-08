
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

# Explicitly install pytest and add diagnostic output
RUN pip install pytest --upgrade && \
    pip list | grep pytest && \
    which pytest && \
    python -c "import sys; print(sys.path)"

# Set environment variables
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV TEST_COMMAND="python -m pytest"

# Print environment info for debugging
RUN echo "Python version:" && python --version
RUN echo "Pytest version:" && python -m pytest --version
RUN echo "PATH:" && echo $PATH
RUN echo "PYTHONPATH:" && echo $PYTHONPATH

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8003"]
