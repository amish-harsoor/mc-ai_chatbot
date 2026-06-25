# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for psycopg2 and potentially other native extensions
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Ensure Python can find the src module
ENV PYTHONPATH=/app

# For the React frontend widget (served separately or via proxy in prod):
#   Set VITE_API_BASE_URL at build time if bundling the UI, or pass at runtime via hosting.
#   The widget defaults to http://localhost:8000 when no env is present.

# Command to run the application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
