#!/usr/bin/env bash
# Render Startup Script
# exit on error
set -o errexit

echo "=================================================="
echo "🚀 Starting Prompt Governance Engine Application..."
echo "=================================================="

# Navigate to the Backend folder
cd Backend

# Add the src folder to PYTHONPATH to ensure correct module imports
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run database migrations using Alembic
echo "Running database migrations..."
cd migrations
alembic upgrade head
cd ..
echo "✓ Database migrations completed successfully."

# Run application using uvicorn
echo "Starting FastAPI server on port ${PORT:-10000} with ${WORKERS:-4} workers..."
exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers ${WORKERS:-4}
