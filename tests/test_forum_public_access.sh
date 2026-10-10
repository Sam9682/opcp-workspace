#!/bin/bash

echo "🧪 Test de l'accès public au forum"
echo "===================================="
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# URL de l'API
API_URL="http://localhost:8000"

echo "📝 Tests à effectuer manuellement:"
echo ""
echo "1. Test de l'endpoint public (sans authentification):"
echo "   ${YELLOW}curl ${API_URL}/api/forum/topics/public${NC}"
echo ""
echo "2. Test de l'interface utilisateur:"
echo "   a) Ouvrir http://localhost:5173 sans être connecté"
echo "   b) Vérifier que les topics du forum s'affichent"
echo "   c) Vérifier que les topics ne sont PAS cliquables"
echo "   d) Vérifier le badge '🔒 Connexion requise'"
echo "   e) Vérifier le message d'information bleu"
echo ""
echo "3. Test avec utilisateur connecté:"
echo "   a) Se connecter à l'application"
echo "   b) Vérifier que les topics sont cliquables"
echo "   c) Vérifier que le widget Oracle s'affiche"
echo "   d) Cliquer sur un topic et vérifier l'accès"
echo ""
echo "4. Test de protection des endpoints:"
echo "   a) Essayer d'accéder à /forum/topics/{id} sans être connecté"
echo "   b) Vérifier la redirection vers /login"
echo ""

# Test automatique de l'endpoint public
echo "🔍 Test automatique de l'endpoint public..."
echo ""

if command -v curl &> /dev/null; then
    echo "Requête: GET ${API_URL}/api/forum/topics/public"
    response=$(curl -s -w "\n%{http_code}" "${API_URL}/api/forum/topics/public" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ Endpoint public accessible (HTTP 200)${NC}"
        echo "Réponse:"
        echo "$body" | head -20
        if [ $(echo "$body" | wc -l) -gt 20 ]; then
            echo "... (tronqué)"
        fi
    else
        echo -e "${RED}❌ Erreur: HTTP $http_code${NC}"
        echo "Réponse:"
        echo "$body"
    fi
else
    echo -e "${YELLOW}⚠️  curl n'est pas installé, test automatique ignoré${NC}"
fi

echo ""
echo "===================================="
echo "📚 Documentation: FORUM_PUBLIC_ACCESS_SUMMARY.md"
echo ""

