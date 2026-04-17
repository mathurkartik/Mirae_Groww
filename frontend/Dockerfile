# frontend/Dockerfile
FROM node:20-slim

WORKDIR /app

# Install dependencies first (better caching)
COPY frontend/package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY frontend/ ./

# Build the application
RUN npm run build

# Expose the frontend port
EXPOSE 3000

# Start command
CMD ["npm", "run", "dev"]
