#!/bin/bash
# Simple startup script for local development

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting Smart Prompt Parser...${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found. Running setup...${NC}"
    make setup
fi

# Activate virtual environment
source venv/bin/activate

# Check if config exists
if [ ! -f "config/config.yaml" ]; then
    echo -e "${YELLOW}⚠ Config file not found. Creating from example...${NC}"
    cp config/config.example.yaml config/config.yaml
    echo -e "${YELLOW}⚠ Please update config/config.yaml with your Portkey API key!${NC}"
fi

# Start Docker services
echo -e "${GREEN}Starting Docker services...${NC}"
make up

# Wait a bit for services to be ready
echo "Waiting for services to be ready..."
sleep 3

# Run migrations
echo -e "${GREEN}Running database migrations...${NC}"
make migrate

# Start application
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Starting Application${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Application will be available at:"
echo -e "  ${YELLOW}API:${NC}      http://localhost:8000"
echo -e "  ${YELLOW}Docs:${NC}     http://localhost:8000/docs"
echo -e "  ${YELLOW}Frontend:${NC} http://localhost:8000"
echo ""
echo -e "${GREEN}Press Ctrl+C to stop${NC}"
echo ""

# Start the application
make dev

