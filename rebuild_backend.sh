#!/bin/bash

echo "=== Rebuilding Backend Container with Quote Fix ==="
echo ""

echo "Step 1: Stopping the backend container..."
docker-compose stop ai-OPCP

echo ""
echo "Step 2: Rebuilding the container with updated code..."
docker-compose build ai-OPCP

echo ""
echo "Step 3: Starting the container..."
docker-compose up -d ai-OPCP

echo ""
echo "Step 4: Waiting for container to start..."
sleep 5

echo ""
echo "Step 5: Checking container status..."
docker-compose ps ai-OPCP

echo ""
echo "Step 6: Checking logs..."
docker-compose logs --tail=30 ai-OPCP

echo ""
echo "=== Rebuild Complete ==="
echo "The quote escaping issue should now be fixed."
echo "Test with a query containing quotes like: écrit une page web qui explique \"l'impact de l'IA sur l'emploi\""
