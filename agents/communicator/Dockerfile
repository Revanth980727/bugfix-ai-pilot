
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Create necessary directories
RUN mkdir -p /app/utils

# Ensure Python can find modules by creating symlink to utils
RUN ln -sf /app/agents/utils /app/utils

# Set Python path to include the app directory
ENV PYTHONPATH=/app

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8004"]
