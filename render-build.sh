#!/usr/bin/env bash
# Render Build Script
# exit on error
set -o errexit

echo "=================================================="
echo "🚀 Building Prompt Governance Engine..."
echo "=================================================="

# Navigate to the Backend folder containing pyproject.toml / requirements.txt
cd Backend

echo "Python version:"
python --version

# Upgrade pip to ensure secure and fast installations
python -m pip install --upgrade pip

# Install production dependencies
echo "Installing Python dependencies..."
python -m pip install -r requirements.txt

# Ensure configuration directory exists and template is copied
if [ ! -f "config/config.yaml" ]; then
    echo "Creating config.yaml from config.example.yaml..."
    cp config/config.example.yaml config/config.yaml
fi

echo "=================================================="
echo "✓ Build complete!"
echo "=================================================="
