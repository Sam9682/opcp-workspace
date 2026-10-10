# Guide de Restauration depuis OVH Object Storage

## Votre Situation

Backup disponible : `s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz`  
Application : `~/deployments/admin/ai-OPCP`  
Profil AWS : `OVH-SWAUTOMORPH`

## Méthode 1 : Restauration Rapide (Recommandée)

### Étape 1 : Télécharger le backup depuis OVH

```bash
cd ~/deployments/admin/ai-OPCP

# Créer le répertoire de sauvegarde
mkdir -p backups

# Télécharger depuis OVH avec AWS CLI
aws s3 cp s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz \
  backups/ \
  --profile OVH-SWAUTOMORPH
```

### Étape 2 : Décompresser le backup

```bash
# Décompresser le fichier .gz
gunzip backups/OPCP_backup_20260220_160349.sql.gz

# Vérifier que le fichier existe
ls -lh backups/OPCP_backup_20260220_160349.sql
```

### Étape 3 : Charger les variables d'environnement

```bash
# Charger le .env
cd ~/deployments/admin/ai-OPCP
export $(cat .env | grep -v '^#' | xargs)

# Vérifier DATABASE_URL
echo $DATABASE_URL
```

### Étape 4 : Restaurer la base de données

```bash
# Utiliser le script de restauration
python3 scripts/restore_database.py backups/OPCP_backup_20260220_160349.sql
```

## Méthode 2 : Restauration Directe avec pg_restore

Si vous préférez utiliser directement pg_restore :

```bash
cd ~/deployments/admin/ai-OPCP

# Télécharger et décompresser
aws s3 cp s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz \
  backups/ \
  --profile OVH-SWAUTOMORPH

gunzip backups/OPCP_backup_20260220_160349.sql.gz

# Charger les variables d'environnement
export $(cat .env | grep -v '^#' | xargs)

# Parser DATABASE_URL (exemple: postgresql://user:pass@host:5432/dbname)
DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')

# Restaurer avec pg_restore
PGPASSWORD=$DB_PASS pg_restore \
  -h $DB_HOST \
  -p $DB_PORT \
  -U $DB_USER \
  -d $DB_NAME \
  --clean \
  --if-exists \
  backups/OPCP_backup_20260220_160349.sql
```

## Méthode 3 : Restauration avec Docker

Si votre application tourne dans Docker :

```bash
cd ~/deployments/admin/ai-OPCP

# Télécharger et décompresser
aws s3 cp s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz \
  backups/ \
  --profile OVH-SWAUTOMORPH

gunzip backups/OPCP_backup_20260220_160349.sql.gz

# Copier dans le conteneur
docker cp backups/OPCP_backup_20260220_160349.sql <container_name>:/app/backups/

# Restaurer depuis le conteneur
docker exec -it <container_name> python scripts/restore_database.py backups/OPCP_backup_20260220_160349.sql
```

## Méthode 4 : Script Automatisé Complet

Créez un script pour automatiser tout le processus :

```bash
#!/bin/bash
# restore_from_ovh.sh

set -e  # Arrêter en cas d'erreur

APP_DIR=~/deployments/admin/ai-OPCP
S3_PATH="s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz"
PROFILE="OVH-SWAUTOMORPH"
BACKUP_DIR="$APP_DIR/backups"

echo "🔄 Restauration de la base de données depuis OVH..."

# Créer le répertoire
mkdir -p "$BACKUP_DIR"

# Télécharger
echo "⬇️  Téléchargement depuis OVH..."
aws s3 cp "$S3_PATH" "$BACKUP_DIR/" --profile "$PROFILE"

# Décompresser
echo "📦 Décompression..."
BACKUP_FILE="$BACKUP_DIR/OPCP_backup_20260220_160349.sql.gz"
gunzip -f "$BACKUP_FILE"

# Restaurer
echo "🔄 Restauration..."
cd "$APP_DIR"
export $(cat .env | grep -v '^#' | xargs)
python3 scripts/restore_database.py "$BACKUP_DIR/OPCP_backup_20260220_160349.sql"

echo "✅ Restauration terminée!"
```

Utilisation :
```bash
chmod +x restore_from_ovh.sh
./restore_from_ovh.sh
```

## Vérification Après Restauration

```bash
cd ~/deployments/admin/ai-OPCP

# Charger les variables
export $(cat .env | grep -v '^#' | xargs)

# Se connecter à la base
psql $DATABASE_URL

# Vérifier les tables
\dt

# Vérifier les utilisateurs
SELECT COUNT(*) FROM users;

# Vérifier les topics du forum
SELECT COUNT(*) FROM forum_topics;

# Quitter
\q
```

## Dépannage

### Erreur : "gunzip: file already exists"

```bash
# Forcer la décompression
gunzip -f backups/OPCP_backup_20260220_160349.sql.gz
```

### Erreur : "pg_restore: command not found"

```bash
# Installer PostgreSQL client
sudo apt-get update
sudo apt-get install postgresql-client
```

### Erreur : "DATABASE_URL not set"

```bash
# Vérifier le fichier .env
cat ~/deployments/admin/ai-OPCP/.env | grep DATABASE_URL

# Charger manuellement
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```

### Erreur : "Access Denied" (OVH)

```bash
# Vérifier le profil AWS
aws configure list --profile OVH-SWAUTOMORPH

# Reconfigurer si nécessaire
aws configure --profile OVH-SWAUTOMORPH
```

### Erreur : "Connection refused" (PostgreSQL)

```bash
# Vérifier que PostgreSQL est démarré
sudo systemctl status postgresql

# Ou si Docker
docker ps | grep postgres
```

## Notes Importantes

⚠️ **ATTENTION** : La restauration écrasera toutes les données actuelles de la base de données !

✅ **Sauvegarde préventive** : Avant de restaurer, créez une sauvegarde de la base actuelle :
```bash
cd ~/deployments/admin/ai-OPCP
python3 scripts/backup_database_universal.py --s3-provider ovh --s3-bucket ai-OPCP
```

✅ **Test** : Si possible, testez d'abord la restauration sur une base de données de test.

✅ **Arrêt de l'application** : Arrêtez l'application pendant la restauration pour éviter les conflits :
```bash
# Si systemd
sudo systemctl stop OPCP

# Si Docker
docker-compose down

# Restaurer...

# Redémarrer
sudo systemctl start OPCP
# ou
docker-compose up -d
```

## Commande Complète en Une Ligne

Pour une restauration rapide :

```bash
cd ~/deployments/admin/ai-OPCP && \
mkdir -p backups && \
aws s3 cp s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz backups/ --profile OVH-SWAUTOMORPH && \
gunzip -f backups/OPCP_backup_20260220_160349.sql.gz && \
export $(cat .env | grep -v '^#' | xargs) && \
python3 scripts/restore_database.py backups/OPCP_backup_20260220_160349.sql
```

## Support

Si vous rencontrez des problèmes :
1. Vérifiez les logs : `tail -f /var/log/OPCP_backup.log`
2. Consultez la documentation : `scripts/README_BACKUP.md`
3. Vérifiez la connexion OVH : `aws s3 ls ai-OPCP/ --profile OVH-SWAUTOMORPH`
