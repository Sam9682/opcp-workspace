#!/bin/bash

# Script d'installation de kiro-cli pour le module Oracle AI
# Ce script doit être exécuté sur Ubuntu/Linux

echo "🔮 Installation de kiro-cli pour le module Oracle AI"
echo "=================================================="

# Vérifier si kiro-cli est déjà installé
if command -v kiro-cli &> /dev/null; then
    echo "✅ kiro-cli est déjà installé"
    kiro-cli --version
    exit 0
fi

echo "📦 Installation de kiro-cli..."

# Note: Remplacer par les vraies commandes d'installation de kiro-cli
# Ceci est un exemple - adapter selon la documentation officielle de Kiro

# Option 1: Installation via npm (si disponible)
if command -v npm &> /dev/null; then
    echo "Installation via npm..."
    npm install -g kiro-cli
fi

# Option 2: Installation via curl (si disponible)
# curl -fsSL https://kiro.ai/install.sh | bash

# Option 3: Installation manuelle
# Télécharger le binaire depuis le site officiel

# Vérifier l'installation
if command -v kiro-cli &> /dev/null; then
    echo "✅ kiro-cli installé avec succès!"
    kiro-cli --version
else
    echo "❌ Échec de l'installation de kiro-cli"
    echo "Veuillez consulter la documentation officielle: https://kiro.ai/docs"
    exit 1
fi

echo ""
echo "🎉 Installation terminée!"
echo "Vous pouvez maintenant utiliser le module Oracle AI avec le fournisseur Kiro"
