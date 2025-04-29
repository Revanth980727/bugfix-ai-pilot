
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent code to the correct location
COPY ./communicator/agent.py /app/
COPY ./utils /app/utils/

# Create necessary directories
RUN mkdir -p /app/utils

# Make sure uvicorn is in the PATH
ENV PATH="/usr/local/bin:${PATH}"

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8004"]
