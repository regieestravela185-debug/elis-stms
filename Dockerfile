# Use Python 3.11.9 (compatible with eventlet/Socket.IO)
FROM python:3.11.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    EVENTLET_NO_GREENDNS=yes

# Set working directory
WORKDIR /app

# Install system dependencies for PostgreSQL and image processing
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create upload directory
RUN mkdir -p app/static/uploads

# Expose port (Render will set this via $PORT)
EXPOSE 5000

# Start with gunicorn using eventlet worker
CMD gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT run:app
