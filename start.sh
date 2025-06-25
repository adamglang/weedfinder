#!/bin/bash

# WeedFinder.ai POC Startup Script

echo "🌿 Starting WeedFinder.ai POC..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your actual credentials before continuing."
    exit 1
fi

# Initialize database
echo "Initializing database..."
python init_db.py

# Run ingestion
echo "Running data ingestion..."
python ingest.py

# Run tests
echo "Running tests..."
python test_poc.py

# Start the API server
echo "Starting API server..."
echo "🚀 WeedFinder.ai POC is starting at http://localhost:8000"
echo "📱 Open ../weedfinder-client/index.html in your browser to test the search"
echo "🛑 Press Ctrl+C to stop the server"
python app.py