
FROM python:3.11-slim

WORKDIR /app

# Install git and other essential tools
RUN apt-get update && \
    apt-get install -y git curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs && chmod 777 /app/logs
RUN mkdir -p /app/code_repo && chmod 777 /app/code_repo

COPY . .

# Set up environment variables - ensure PYTHONPATH includes the current directory
ENV PYTHONPATH=/app

# Explicitly install all required packages including diff-match-patch
RUN pip install --no-cache-dir PyGithub unidiff diff-match-patch && \
    python -c "import github; import unidiff; import diff_match_patch; print('All required modules can be imported successfully')"

# Verify environment and modules on container start
RUN python -c "from backend.env import verify_required_modules, log_environment_status; log_environment_status(); verify_required_modules()" || echo "Environment verification completed with warnings"

# Run the orchestrator with the correct Python module path
CMD ["python", "-m", "orchestrator.start_orchestrator"]
