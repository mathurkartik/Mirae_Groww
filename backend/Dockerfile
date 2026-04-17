# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for ChromaDB and other libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the application
# We copy the ingestion folder too as the backend might depend on retrieval logic there
COPY backend/ ./backend/
COPY ingestion/ ./ingestion/
COPY data/ ./data/

# Expose the API port
EXPOSE 8000

# Start command
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
