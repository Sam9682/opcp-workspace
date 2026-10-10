#!/bin/bash

# OPCP Deployment Script
# This script safely stops and starts the application while preserving data

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== OPCP Deployment Script ===${NC}"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found, copying from .env.example"
    cp .env.example .env
    print_warning "Please edit .env file with your configuration"
fi

# Stop containers WITHOUT removing volumes
print_info "Stopping containers (preserving data)..."
docker-compose stop

# Remove containers but keep volumes
print_info "Removing old containers (volumes will be preserved)..."
docker-compose rm -f

# Pull latest images if needed
print_info "Pulling latest images..."
docker-compose pull || true

# Rebuild images
print_info "Building images..."
docker-compose build

# Start containers
print_info "Starting containers..."
docker-compose up -d

# Wait for database to be ready
print_info "Waiting for database to be ready..."
sleep 5

# Check if postgres is healthy
print_info "Checking database health..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U OPCP_user -d OPCP_db > /dev/null 2>&1; then
        print_info "Database is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Database failed to start"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Run database migrations
print_info "Running database migrations..."
docker-compose exec -T ai-OPCP alembic upgrade head || print_warning "Migration failed or already up to date"

# Show container status
print_info "Container status:"
docker-compose ps

# Show volume information
print_info "Data volumes:"
docker volume ls | grep postgres_data || print_warning "No postgres_data volume found"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Application URLs:"
echo "  - API: http://localhost:${HTTP_PORT:-6000}"
echo "  - Frontend: http://localhost:${HTTP_PORT2:-6003}"
echo "  - HTTPS: https://localhost:${HTTPS_PORT:-6001}"
echo "  - API Docs: http://localhost:${HTTP_PORT:-6000}/docs"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose stop"
echo "To restart: ./scripts/deploy.sh"
