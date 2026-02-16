# Use standard Python 3.11 slim base image for Bedrock AgentCore
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first (better layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    find /usr/local -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local -type f -name "*.pyc" -delete && \
    find /usr/local -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Copy application source
COPY src/ ./src/

# ✅ Copy knowledge base data into the container
COPY data/ ./data/

# ✅ Explicitly define data directory for the app
ENV DATA_DIR=/app/data

# Expose port 8080 (Bedrock AgentCore requirement)
EXPOSE 8080

# Run FastAPI with uvicorn on port 8080
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
