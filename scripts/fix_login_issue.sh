#!/bin/bash
# Script to diagnose and fix login issues

echo "=== OPCP Login Issue Troubleshooting ==="
echo ""

# Check if containers are running
echo "1. Checking Docker containers..."
docker-compose ps

echo ""
echo "2. Checking backend health..."
curl -s http://ai-OPCP:6000/health | jq . || echo "❌ Backend not responding"

echo ""
echo "3. Checking if admin user exists and is properly configured..."
docker-compose exec ai-OPCP python3 scripts/verify_admin_user.py

echo ""
echo "4. Testing API endpoint directly..."
echo "Attempting login with admin@opcp-psmc.com..."
curl -X POST http://ai-OPCP:6000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@opcp-psmc.com","password":"Admin1234!"}' \
  -v

echo ""
echo ""
echo "5. Checking nginx logs for errors..."
docker-compose logs --tail=50 nginx | grep -i error || echo "No errors in nginx logs"

echo ""
echo "6. Checking backend logs for errors..."
docker-compose logs --tail=50 ai-OPCP | grep -i error || echo "No errors in backend logs"

echo ""
echo "=== Troubleshooting Complete ==="
echo ""
echo "Common issues and solutions:"
echo "1. Email not verified: Run 'docker-compose exec ai-OPCP python3 scripts/verify_admin_user.py'"
echo "2. Wrong password: Default is 'Admin1234!' (capital A, exclamation at end)"
echo "3. API not accessible: Check if backend is running on port 6000"
echo "4. CORS issues: Check browser console for CORS errors"
