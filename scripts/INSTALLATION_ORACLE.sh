#!/bin/bash

echo "🔮 Installation du module Oracle AI"
echo "===================================="
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction de vérification
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1"
        return 1
    fi
}

# Vérifier les fichiers
echo "📦 Vérification des fichiers..."
echo ""

all_ok=true

# Backend
echo "Backend:"
check_file "app/oracle/__init__.py" || all_ok=false
check_file "app/oracle/router.py" || all_ok=false
check_file "app/oracle/service.py" || all_ok=false
check_file "app/oracle/schemas.py" || all_ok=false
check_file "app/oracle/ai_providers.py" || all_ok=false
check_file "app/models/oracle.py" || all_ok=false

echo ""
echo "Frontend:"
check_file "frontend/src/pages/OraclePage.tsx" || all_ok=false
check_file "frontend/src/components/OracleWidget.tsx" || all_ok=false
check_file "frontend/src/services/oracleService.ts" || all_ok=false

echo ""
echo "Documentation:"
check_file "docs/ORACLE_AI_MODULE.md" || all_ok=false
check_file "docs/ORACLE_INTEGRATION_GUIDE.md" || all_ok=false
check_file "docs/ORACLE_QUICK_START.md" || all_ok=false
check_file "docs/ORACLE_INTERNAL_USAGE.md" || all_ok=false
check_file "README_ORACLE.md" || all_ok=false

echo ""
echo "Configuration:"
check_file "oracle_config.json" || all_ok=false
check_file ".env.example" || all_ok=false

echo ""
echo "Scripts:"
check_file "scripts/install_kiro_cli.sh" || all_ok=false
check_file "test_oracle_module.py" || all_ok=false

echo ""
echo "===================================="

if [ "$all_ok" = true ]; then
    echo -e "${GREEN}✅ Tous les fichiers sont présents!${NC}"
    echo ""
    echo "📝 Prochaines étapes:"
    echo ""
    echo "1. Configurer les variables d'environnement:"
    echo "   cp .env.example .env"
    echo "   nano .env  # Ajouter vos clés API"
    echo ""
    echo "2. Exécuter les migrations:"
    echo "   alembic upgrade head"
    echo ""
    echo "3. (Optionnel) Installer kiro-cli:"
    echo "   bash scripts/install_kiro_cli.sh"
    echo ""
    echo "4. Démarrer l'application:"
    echo "   uvicorn app.main:app --reload"
    echo "   cd frontend && npm run dev"
    echo ""
    echo "5. Tester:"
    echo "   Ouvrir http://localhost:5173"
    echo "   Se connecter et cliquer sur '🔮 L'Oracle (AI)'"
    echo ""
    echo "📚 Documentation complète: docs/ORACLE_QUICK_START.md"
    exit 0
else
    echo -e "${RED}❌ Certains fichiers sont manquants${NC}"
    echo "Vérifiez que tous les fichiers ont été créés correctement"
    exit 1
fi
