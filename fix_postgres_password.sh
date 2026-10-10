#!/bin/bash

echo "=== Fixing PostgreSQL Password Authentication ==="
echo ""

# Get the password from .env
POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2)
echo "Password from .env file: $POSTGRES_PASSWORD"
echo ""

echo "Step 1: Connecting to postgres as superuser to change password..."
docker-compose exec postgres psql -U postgres -d OPCP_db -c "ALTER USER OPCP_user WITH PASSWORD '$POSTGRES_PASSWORD';"

echo ""
echo "Step 2: Verifying the password change..."
docker-compose exec postgres psql -U postgres -d OPCP_db -c "SELECT usename FROM pg_user WHERE usename = 'OPCP_user';"

echo ""
echo "Step 3: Testing connection with new password..."
PGPASSWORD=$POSTGRES_PASSWORD docker-compose exec postgres psql -U OPCP_user -d OPCP_db -c "SELECT 'Connection successful!' as status;"

echo ""
echo "Step 4: Fixing alembic_version table..."
docker-compose exec postgres psql -U postgres -d OPCP_db -c "DELETE FROM alembic_version;"
docker-compose exec postgres psql -U postgres -d OPCP_db -c "INSERT INTO alembic_version (version_num) VALUES ('b4bf46d2c974');"

echo ""
echo "Step 5: Verifying alembic_version..."
docker-compose exec postgres psql -U postgres -d OPCP_db -c "SELECT * FROM alembic_version;"

echo ""
echo "Step 6: Restarting backend container..."
docker-compose restart ai-OPCP

echo ""
echo "Step 7: Watching logs (Ctrl+C to exit)..."
sleep 3
docker-compose logs -f ai-OPCP
