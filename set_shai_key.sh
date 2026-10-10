#!/bin/bash

echo "=== Setting SHAI_API_KEY in Container ==="
echo ""

# Your SHAI API key
SHAI_KEY="eyJhbGciOiJFZERTQSIsImtpZCI6IjgzMkFGNUE5ODg3MzFCMDNGM0EzMTRFMDJFRUJFRjBGNDE5MUY0Q0YiLCJraW5kIjoicGF0IiwidHlwIjoiSldUIn0.eyJ0b2tlbiI6ImR1QUNINVIrUFd3cWxOVldweThvTVlZUTQxL2JINE5LQklqSGRuc0t1YW89In0.TKhF8WIz6E8HmvbpbRsDX76MfJXiYylSEprFjZNF48L4J-ZwsqzoLhNLHlMvOJSTZmrYt-BEIG9ur39UJzb6CQ"

echo "Option 1: Set in .env file (RECOMMENDED - persists across container restarts)"
echo ""
read -p "Do you want to add SHAI_API_KEY to .env file? (y/n): " add_to_env

if [ "$add_to_env" = "y" ]; then
    # Check if SHAI_API_KEY already exists in .env
    if grep -q "^SHAI_API_KEY=" .env 2>/dev/null; then
        echo "Updating existing SHAI_API_KEY in .env..."
        sed -i "s|^SHAI_API_KEY=.*|SHAI_API_KEY=$SHAI_KEY|" .env
    else
        echo "Adding SHAI_API_KEY to .env..."
        echo "" >> .env
        echo "# Shai AI Configuration" >> .env
        echo "SHAI_API_KEY=$SHAI_KEY" >> .env
        echo "SHAI_API_URL=https://api.ovh.com/shai/v1/chat" >> .env
    fi
    
    echo ""
    echo "✓ SHAI_API_KEY added to .env file"
    echo ""
    echo "Restarting container to apply changes..."
    docker-compose restart ai-OPCP
    
    echo ""
    echo "Verifying environment variable in container..."
    sleep 3
    docker-compose exec ai-OPCP printenv SHAI_API_KEY | head -c 50
    echo "..."
else
    echo ""
    echo "Option 2: Set temporarily in running container (lost on restart)"
    echo ""
    read -p "Do you want to set it temporarily? (y/n): " set_temp
    
    if [ "$set_temp" = "y" ]; then
        echo "Setting SHAI_API_KEY in container..."
        docker exec ai-OPCP-app-1-6136 /bin/sh -c "export SHAI_API_KEY='$SHAI_KEY'"
        
        echo ""
        echo "Note: This is temporary and will be lost when the container restarts."
        echo "For permanent configuration, add it to the .env file."
    fi
fi

echo ""
echo "=== Done ==="
