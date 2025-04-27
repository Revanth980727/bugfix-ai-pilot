
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the mount point exists
RUN mkdir -p /app/code_repo

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8001"]
