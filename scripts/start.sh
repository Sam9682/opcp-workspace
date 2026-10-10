#!/bin/bash

# OPCP Start Script
# Starts the application with existing data

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Starting OPCP Application ===${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}[WARNING]${NC} .env file not found, copying from .env.example"
    cp .env.example .env
    echo -e "${YELLOW}[WARNING]${NC} Please edit .env file with your configuration"
fi

# Start containers
echo -e "${GREEN}Starting containers...${NC}"
docker-compose up -d

# Wait for database to be ready
echo -e "${GREEN}Waiting for database to be ready...${NC}"
sleep 5

for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U OPCP_user -d OPCP_db > /dev/null 2>&1; then
        echo -e "${GREEN}Database is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}[ERROR]${NC} Database failed to start"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Show container status
echo ""
echo -e "${GREEN}Container status:${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}=== Application Started Successfully ===${NC}"
echo ""
echo "Application URLs:"
echo "  - API: http://localhost:${HTTP_PORT:-6000}"
echo "  - Frontend: http://localhost:${HTTP_PORT2:-6003}"
echo "  - HTTPS: https://localhost:${HTTPS_PORT:-6001}"
echo "  - API Docs: http://localhost:${HTTP_PORT:-6000}/docs"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: ./scripts/stop.sh"
