#!/bin/bash
# Setup script for local development

set -e

echo "🚀 Setting up Smart Prompt Parser & Canonicalisation Engine"
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.11+ is required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python version: $(python3 --version)"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements-dev.txt --quiet
echo "✓ Dependencies installed"

# Create config file if it doesn't exist
echo ""
if [ ! -f "config/config.yaml" ]; then
    echo "Creating config file from example..."
    cp config/config.example.yaml config/config.yaml
    echo "✓ Config file created"
    echo ""
    echo "⚠️  IMPORTANT: Update config/config.yaml with your settings!"
else
    echo "✓ Config file already exists"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env 2>/dev/null || true
    echo "✓ .env file created (if .env.example exists)"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Update config/config.yaml with your settings"
echo "  2. Run 'make up' to start Docker services"
echo "  3. Run 'make migrate' to set up database"
echo "  4. Run 'make dev' to start the application"
echo ""
echo "Or use 'make quickstart' to do everything at once!"

