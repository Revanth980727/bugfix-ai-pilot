
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent code to the correct location
COPY ./planner/agent.py /app/
COPY ./utils /app/utils/

# Create necessary directories with proper permissions
RUN mkdir -p /app/code_repo && chmod 777 /app/code_repo
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Make sure uvicorn is in the PATH
ENV PATH="/usr/local/bin:${PATH}"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8001"]
