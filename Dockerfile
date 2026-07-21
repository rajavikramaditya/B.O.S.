FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements
COPY backend/requirements.txt .

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY backend/ /app/backend/

# Copy frontend files
COPY frontend/ /app/frontend/

# Create necessary directories and placeholder files
RUN mkdir -p /app/backend/playout/voice_assets /app/backend/playout/local_voices /app/backend/logs && \
    touch /app/backend/radio_station.db

# Expose backend port (configurable, default 8000)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

# Create non-root user and assign permissions
RUN groupadd -r neena && useradd -r -g neena neena && \
    chown -R neena:neena /app

# Run as non-root user
USER neena

# CMD to start the backend application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
