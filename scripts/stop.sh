#!/bin/bash

# OPCP Stop Script
# Safely stops the application while preserving all data

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Stopping OPCP Application ===${NC}"

# Stop containers WITHOUT removing volumes
echo -e "${YELLOW}Stopping containers (data will be preserved)...${NC}"
docker-compose stop

echo -e "${GREEN}Application stopped successfully!${NC}"
echo ""
echo "Data volumes are preserved. To start again, run:"
echo "  ./scripts/start.sh"
echo ""
echo "To completely remove everything including data (DANGEROUS):"
echo "  docker-compose down -v"
