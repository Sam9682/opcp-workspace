#!/bin/bash

echo "=== Configuring SHAI AI Provider ==="
echo ""

SHAI_KEY="eyJhbGciOiJFZERTQSIsImtpZCI6IjgzMkFGNUE5ODg3MzFCMDNGM0EzMTRFMDJFRUJFRjBGNDE5MUY0Q0YiLCJraW5kIjoicGF0IiwidHlwIjoiSldUIn0.eyJ0b2tlbiI6ImR1QUNINVIrUFd3cWxOVldweThvTVlZUTQxL2JINE5LQklqSGRuc0t1YW89In0.TKhF8WIz6E8HmvbpbRsDX76MfJXiYylSEprFjZNF48L4J-ZwsqzoLhNLHlMvOJSTZmrYt-BEIG9ur39UJzb6CQ"

echo "Step 1: Checking if SHAI_API_KEY exists in .env..."
if grep -q "^SHAI_API_KEY=" .env 2>/dev/null; then
    echo "  ✓ SHAI_API_KEY found, updating..."
    sed -i "s|^SHAI_API_KEY=.*|SHAI_API_KEY=$SHAI_KEY|" .env
else
    echo "  Adding SHAI_API_KEY to .env..."
    echo "" >> .env
    echo "# Shai AI Configuration (OVH)" >> .env
    echo "SHAI_API_KEY=$SHAI_KEY" >> .env
fi

echo ""
echo "Step 2: Checking if SHAI_API_URL exists in .env..."
if grep -q "^SHAI_API_URL=" .env 2>/dev/null; then
    echo "  Updating SHAI_API_URL to use EU endpoint..."
    sed -i "s|^SHAI_API_URL=.*|SHAI_API_URL=https://oai.endpoints.kepler.ai.cloud.ovh.net/v1|" .env
else
    echo "  Adding SHAI_API_URL to .env..."
    echo "SHAI_API_URL=https://oai.endpoints.kepler.ai.cloud.ovh.net/v1" >> .env
fi

echo ""
echo "Step 3: Verifying .env configuration..."
echo "  SHAI_API_KEY: $(grep '^SHAI_API_KEY=' .env | cut -c1-50)..."
echo "  SHAI_API_URL: $(grep '^SHAI_API_URL=' .env)"

echo ""
echo "Step 4: Rebuilding backend container with updated configuration..."
docker-compose stop ai-OPCP
docker-compose build ai-OPCP
docker-compose up -d ai-OPCP

echo ""
echo "Step 5: Waiting for container to start..."
sleep 5

echo ""
echo "Step 6: Verifying environment variables in container..."
echo "  SHAI_API_KEY in container:"
docker-compose exec ai-OPCP printenv SHAI_API_KEY | head -c 50
echo "..."
echo ""
echo "  SHAI_API_URL in container:"
docker-compose exec ai-OPCP printenv SHAI_API_URL

echo ""
echo "Step 7: Testing Python config loading..."
docker-compose exec ai-OPCP python -c "from app.config import settings; print(f'SHAI_API_KEY loaded: {bool(settings.SHAI_API_KEY)}'); print(f'SHAI_API_URL: {settings.SHAI_API_URL}')"

echo ""
echo "=== Configuration Complete ==="
echo ""
echo "✓ SHAI_API_KEY configured in .env"
echo "✓ Backend container rebuilt"
echo "✓ Environment variables verified"
echo ""
echo "You can now use Shai AI provider in L'Oracle page!"
echo ""
echo "Checking logs..."
docker-compose logs --tail=20 ai-OPCP
