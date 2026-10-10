#!/bin/bash
# Script de restauration rapide depuis OVH Object Storage
# Usage: ./restore_from_ovh_quick.sh

set -e  # Arrêter en cas d'erreur

# Configuration
APP_DIR=~/deployments/admin/ai-OPCP
S3_BUCKET="ai-OPCP"
S3_KEY="10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz"
AWS_PROFILE="OVH-SWAUTOMORPH"
BACKUP_DIR="$APP_DIR/backups"

echo "=========================================="
echo "🔄 Restauration depuis OVH Object Storage"
echo "=========================================="
echo ""
echo "Backup: s3://$S3_BUCKET/$S3_KEY"
echo "Application: $APP_DIR"
echo "Profil AWS: $AWS_PROFILE"
echo ""

# Vérifier que le répertoire de l'application existe
if [ ! -d "$APP_DIR" ]; then
    echo "❌ Erreur: Le répertoire $APP_DIR n'existe pas"
    exit 1
fi

# Créer le répertoire de sauvegarde
mkdir -p "$BACKUP_DIR"

# Télécharger depuis OVH
echo "⬇️  Étape 1/4: Téléchargement depuis OVH..."
aws s3 cp "s3://$S3_BUCKET/$S3_KEY" "$BACKUP_DIR/" --profile "$AWS_PROFILE"

if [ $? -ne 0 ]; then
    echo "❌ Erreur lors du téléchargement"
    exit 1
fi

BACKUP_FILE_GZ="$BACKUP_DIR/OPCP_backup_20260220_160349.sql.gz"
BACKUP_FILE="$BACKUP_DIR/OPCP_backup_20260220_160349.sql"

# Vérifier que le fichier a été téléchargé
if [ ! -f "$BACKUP_FILE_GZ" ]; then
    echo "❌ Erreur: Le fichier $BACKUP_FILE_GZ n'a pas été téléchargé"
    exit 1
fi

FILE_SIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
echo "✅ Téléchargement réussi! Taille: $FILE_SIZE"
echo ""

# Décompresser
echo "📦 Étape 2/4: Décompression..."
gunzip -f "$BACKUP_FILE_GZ"

if [ $? -ne 0 ]; then
    echo "❌ Erreur lors de la décompression"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Erreur: Le fichier décompressé n'existe pas"
    exit 1
fi

UNCOMPRESSED_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Décompression réussie! Taille: $UNCOMPRESSED_SIZE"
echo ""

# Charger les variables d'environnement
echo "🔧 Étape 3/4: Chargement de la configuration..."
cd "$APP_DIR"

if [ ! -f ".env" ]; then
    echo "❌ Erreur: Le fichier .env n'existe pas dans $APP_DIR"
    exit 1
fi

export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)

if [ -z "$DATABASE_URL" ]; then
    echo "❌ Erreur: DATABASE_URL n'est pas défini dans .env"
    exit 1
fi

echo "✅ Configuration chargée"
echo ""

# Confirmation
echo "⚠️  ATTENTION: Cette opération va écraser la base de données actuelle!"
echo ""
read -p "Êtes-vous sûr de vouloir continuer? (oui/non): " CONFIRM

if [ "$CONFIRM" != "oui" ] && [ "$CONFIRM" != "yes" ] && [ "$CONFIRM" != "o" ] && [ "$CONFIRM" != "y" ]; then
    echo "❌ Restauration annulée"
    exit 0
fi

echo ""

# Restaurer
echo "🔄 Étape 4/4: Restauration de la base de données..."
python3 scripts/restore_database.py "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Restauration terminée avec succès!"
    echo "=========================================="
    echo ""
    echo "Prochaines étapes:"
    echo "1. Vérifier l'application: cd $APP_DIR && docker-compose ps"
    echo "2. Vérifier les logs: docker-compose logs -f"
    echo "3. Tester l'accès: curl http://localhost:6000/health"
    echo ""
else
    echo ""
    echo "❌ Erreur lors de la restauration"
    exit 1
fi
