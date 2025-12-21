FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first to leverage cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Base image mcr.microsoft.com/playwright/python includes browsers, 
# so we don't need to reinstall them.

# Copy the rest of the application
COPY . .

# Create necessary directories for persistence (even if ephemeral)
RUN mkdir -p screenshots logs reports uat_db

# Expose the port Flask runs on
EXPOSE 5000

# Environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the application
# Using gunicorn is better for production, but app.py uses SocketIO with threading mode
# so we stick to the app.py entry point or use a specific worker class if we switch to gunicorn later.
# For now, running python app.py is the safest compatibility path for this specific setup.
CMD ["python", "app.py"]
