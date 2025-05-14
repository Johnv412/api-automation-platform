# Dockerfile for API Integration Platform

# --- Base Stage --- 
# Use an official Python runtime as a parent image
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (if any)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# --- Builder Stage --- 
# This stage is for installing dependencies
FROM base as builder

# Install build tools if necessary (e.g., for compiling certain Python packages)
# RUN pip install --upgrade pip setuptools wheel

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# We use --no-cache-dir to reduce image size slightly for this stage, though it matters more for final stage
# For production, consider using a virtual environment within the Docker image, 
# but for simplicity in a single app container, direct install is common.
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime Stage --- 
# This is the final image that will be run
FROM base as runtime

# Copy the installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Create a non-root user for security (optional but recommended)
# RUN useradd --create-home --shell /bin/bash appuser
# USER appuser
# WORKDIR /home/appuser/app 
# If using a non-root user, ensure file permissions are correct for copied app code.

# For now, sticking to root user for simplicity, but acknowledge non-root is best practice.
WORKDIR /app

# Copy the application code from the host to the image
# Ensure .dockerignore is used to exclude unnecessary files (like .git, venv, __pycache__)
COPY . .

# Create logs directory and set permissions (if it doesn't exist)
# This path should match what's in logging_manager.py or config
RUN mkdir -p /app/logs && chmod -R 755 /app/logs
# If running as non-root, ensure appuser owns this: chown -R appuser:appuser /app/logs

# Expose the port the app runs on (for the main platform, and dashboard if separate)
# The main platform itself might not expose a port unless it has an API for control,
# but the dashboard will.
EXPOSE 5001 # Default dashboard port, adjust if different in config
# If the main platform runs a gRPC/HTTP server for control, expose that too.

# Set the default command to run when the container starts
# This should match how main.py is intended to be run.
# Example: CMD ["python", "main.py", "--config", "config/production.yaml", "--dashboard"]
# The exact command will depend on the desired default startup behavior (e.g., run dashboard, run specific workflow)
# For a general purpose image, it might just be `python main.py` and expect config via ENV or mounted files.

ENV AIP_ENV="production"
ENV AIP_CONFIG_PATH="config/production.yaml" # Example, adjust as needed

# Default command: Start the platform with the dashboard enabled.
# Users can override this when running `docker run` or in `docker-compose.yml`.
CMD ["python3.11", "main.py", "--dashboard"]

