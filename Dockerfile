FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies required for pyttsx3/espeak
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default entrypoint runs the proxy; service containers override command
ENTRYPOINT ["python"]
CMD ["llm_proxy.py"]
