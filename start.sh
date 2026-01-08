#!/bin/bash

# Startup script for Agentic AI Server

set -e

echo "🚀 Starting Agentic AI Server..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration, especially OPENAI_API_KEY"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install it and try again."
    exit 1
fi

# Start services
echo "📦 Starting Docker services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ All services are healthy!"
        echo ""
        echo "📖 API Documentation: http://localhost:8000/docs"
        echo "🔍 Health Check: http://localhost:8000/health"
        echo "📊 Logs: docker-compose logs -f app"
        echo ""
        echo "🎉 Agentic AI Server is running!"
        exit 0
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

echo "⚠️  Services started but health check failed. Check logs with: docker-compose logs app"
exit 1
