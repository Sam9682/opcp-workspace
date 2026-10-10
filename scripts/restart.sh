#!/bin/bash

# OPCP Restart Script
# Restarts the application while preserving data

set -e

echo "=== Restarting OPCP Application ==="
echo ""

# Stop the application
./scripts/stop.sh

echo ""
echo "Waiting 3 seconds before restart..."
sleep 3
echo ""

# Start the application
./scripts/start.sh
