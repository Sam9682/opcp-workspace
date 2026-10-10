#!/bin/bash

# Script de test pour vérifier l'installation de Kiro CLI dans le container

echo "🔮 Test de l'installation de Kiro CLI dans le container Docker"
echo "=============================================================="
echo ""

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour afficher un succès
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Fonction pour afficher une erreur
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Fonction pour afficher un avertissement
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Test 1: Vérifier que le container est en cours d'exécution
echo "Test 1: Vérification du container..."
if docker-compose ps | grep -q "web.*Up"; then
    print_success "Container web est en cours d'exécution"
else
    print_error "Container web n'est pas en cours d'exécution"
    echo "Exécutez: docker-compose up -d"
    exit 1
fi
echo ""

# Test 2: Vérifier que kiro-cli est installé
echo "Test 2: Vérification de l'installation de kiro-cli..."
if docker-compose exec -T web which kiro-cli > /dev/null 2>&1; then
    print_success "kiro-cli est installé"
    VERSION=$(docker-compose exec -T web kiro-cli --version 2>&1 | head -n 1)
    echo "   Version: $VERSION"
else
    print_error "kiro-cli n'est pas installé dans le container"
    echo "   Solution: Reconstruisez le container avec 'docker-compose build --no-cache web'"
    exit 1
fi
echo ""

# Test 3: Vérifier le PATH
echo "Test 3: Vérification du PATH..."
PATH_CHECK=$(docker-compose exec -T web bash -c 'echo $PATH')
if echo "$PATH_CHECK" | grep -q "/root/.local/bin"; then
    print_success "PATH contient /root/.local/bin"
else
    print_warning "PATH ne contient pas /root/.local/bin"
    echo "   PATH actuel: $PATH_CHECK"
fi
echo ""

# Test 4: Test de l'API Oracle
echo "Test 4: Test de l'API Oracle avec Kiro AI..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Dis bonjour en une phrase", "ai_provider": "kiro"}' 2>&1)

if echo "$RESPONSE" | grep -q '"answer"'; then
    print_success "L'API Oracle fonctionne avec Kiro AI"
    echo "   Réponse reçue (extrait):"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null | grep -A 1 '"answer"' | head -n 2 || echo "$RESPONSE" | head -c 200
else
    print_error "L'API Oracle ne fonctionne pas correctement"
    echo "   Réponse: $RESPONSE"
    echo ""
    echo "   Vérifiez les logs: docker-compose logs web | tail -n 50"
fi
echo ""

# Test 5: Vérifier les logs pour les erreurs Kiro
echo "Test 5: Vérification des logs pour les erreurs Kiro..."
ERRORS=$(docker-compose logs web 2>&1 | grep -i "kiro.*error\|kiro-cli.*not found" | tail -n 5)
if [ -z "$ERRORS" ]; then
    print_success "Aucune erreur Kiro trouvée dans les logs"
else
    print_warning "Erreurs Kiro trouvées dans les logs:"
    echo "$ERRORS"
fi
echo ""

# Résumé
echo "=============================================================="
echo "🎉 Tests terminés!"
echo ""
echo "Pour tester manuellement dans l'interface web:"
echo "1. Ouvrez http://localhost:3000"
echo "2. Connectez-vous"
echo "3. Allez dans 'L'Oracle (AI)' 🔮"
echo "4. Vérifiez que 'Kiro AI (Local - Gratuit)' est sélectionné"
echo "5. Posez une question"
echo ""
echo "Pour voir les logs en temps réel:"
echo "   docker-compose logs -f web"
