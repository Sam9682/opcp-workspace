#!/bin/bash

# Direct fix for Alembic revision error
echo "=== Fixing Alembic Revision Error ==="
echo ""

echo "1. Checking current alembic_version in database..."
docker-compose exec postgres psql -U OPCP_user -d OPCP_db -c "SELECT * FROM alembic_version;"

echo ""
echo "2. Deleting the invalid revision 'c5d8e9f1a2b3'..."
docker-compose exec postgres psql -U OPCP_user -d OPCP_db -c "DELETE FROM alembic_version;"

echo ""
echo "3. Setting to the last known good revision 'b4bf46d2c974'..."
docker-compose exec postgres psql -U OPCP_user -d OPCP_db -c "INSERT INTO alembic_version (version_num) VALUES ('b4bf46d2c974');"

echo ""
echo "4. Verifying the fix..."
docker-compose exec postgres psql -U OPCP_user -d OPCP_db -c "SELECT * FROM alembic_version;"

echo ""
echo "5. Checking DATABASE_URL in container..."
docker-compose exec ai-OPCP printenv DATABASE_URL

echo ""
echo "6. Testing database connection from container..."
docker-compose exec ai-OPCP python -c "from app.config import settings; print(f'DB URL: {settings.DATABASE_URL}')" || echo "Failed to load config"

echo ""
echo "7. Restarting the backend container..."
docker-compose restart ai-OPCP

echo ""
echo "8. Checking logs (Ctrl+C to exit)..."
docker-compose logs -f ai-OPCP
