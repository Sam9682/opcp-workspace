#!/bin/bash

echo "=== Force Rebuilding Backend Container (No Cache) ==="
echo ""

echo "Step 1: Stopping all containers..."
docker-compose stop

echo ""
echo "Step 2: Removing Python cache files..."
find app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find app -type f -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "Step 3: Removing old backend container..."
docker-compose rm -f ai-OPCP

echo ""
echo "Step 4: Rebuilding backend with --no-cache..."
docker-compose build --no-cache ai-OPCP

echo ""
echo "Step 5: Starting all services..."
docker-compose up -d

echo ""
echo "Step 6: Waiting for services to start..."
sleep 8

echo ""
echo "Step 7: Checking container status..."
docker-compose ps

echo ""
echo "Step 8: Tailing logs (Ctrl+C to exit)..."
docker-compose logs -f ai-OPCP
