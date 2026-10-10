# Aide-Mémoire - Commandes de Sauvegarde

## Configuration Initiale

```bash
# 1. Installer les dépendances
pip install boto3
sudo apt-get install postgresql-client

# 2. Configurer AWS
aws configure

# 3. Créer le bucket S3
bash scripts/setup_s3_bucket.sh

# 4. Tester la configuration
python scripts/test_backup_setup.py
```

## Sauvegardes

```bash
# Sauvegarde complète (locale + S3)
python scripts/backup_database.py

# Sauvegarde locale uniquement
python scripts/backup_database.py --no-s3

# Sauvegarde avec bucket personnalisé
python scripts/backup_database.py --s3-bucket mon-bucket

# Sauvegarde avec rétention de 60 jours
python scripts/backup_database.py --retention-days 60
```

## Lister les Sauvegardes

```bash
# Sauvegardes locales
python scripts/backup_database.py --list

# Sauvegardes S3 (toutes)
python scripts/restore_from_s3.py list

# Sauvegardes S3 (février 2026)
python scripts/restore_from_s3.py list --prefix 2026/02/

# Sauvegardes S3 (20 février 2026)
python scripts/restore_from_s3.py list --prefix 2026/02/20/
```

## Restauration

```bash
# Restaurer depuis S3 (automatique)
python scripts/restore_from_s3.py restore 2026/02/20/OPCP_backup_20260220_143000.sql

# Télécharger depuis S3 (sans restaurer)
python scripts/restore_from_s3.py download 2026/02/20/OPCP_backup_20260220_143000.sql

# Restaurer depuis un fichier local
python scripts/restore_database.py backups/OPCP_backup_20260220_143000.sql
```

## Gestion S3

```bash
# Lister le contenu du bucket
aws s3 ls s3://ai-OPCP/ --recursive

# Télécharger manuellement un fichier
aws s3 cp s3://ai-OPCP/2026/02/20/OPCP_backup_20260220_143000.sql ./

# Supprimer un fichier
aws s3 rm s3://ai-OPCP/2026/02/20/OPCP_backup_20260220_143000.sql

# Synchroniser toutes les sauvegardes localement
aws s3 sync s3://ai-OPCP/ ./backups-s3/
```

## Automatisation

```bash
# Éditer le crontab
crontab -e

# Exemples de tâches cron:

# Sauvegarde quotidienne à 2h du matin
0 2 * * * cd /path/to/OPCP && python3 scripts/backup_database.py >> /var/log/OPCP_backup.log 2>&1

# Sauvegarde toutes les 6 heures
0 */6 * * * cd /path/to/OPCP && python3 scripts/backup_database.py >> /var/log/OPCP_backup.log 2>&1

# Sauvegarde hebdomadaire (dimanche à 3h)
0 3 * * 0 cd /path/to/OPCP && python3 scripts/backup_database.py >> /var/log/OPCP_backup.log 2>&1

# Voir les logs
tail -f /var/log/OPCP_backup.log
```

## Docker

```bash
# Sauvegarde depuis le conteneur
docker exec -it OPCP-container python scripts/backup_database.py

# Restaurer depuis le conteneur
docker exec -it OPCP-container python scripts/restore_from_s3.py restore 2026/02/20/OPCP_backup_20260220_143000.sql

# Lister les sauvegardes depuis le conteneur
docker exec -it OPCP-container python scripts/restore_from_s3.py list

# Copier un fichier de sauvegarde depuis le conteneur
docker cp OPCP-container:/app/backups/OPCP_backup_20260220_143000.sql ./
```

## Dépannage

```bash
# Tester la configuration complète
python scripts/test_backup_setup.py

# Vérifier la connexion à la base de données
pg_isready -h localhost -p 5432 -U OPCP_user -d OPCP_db

# Vérifier les credentials AWS
aws sts get-caller-identity

# Vérifier l'accès au bucket
aws s3 ls s3://ai-OPCP/

# Tester pg_dump manuellement
pg_dump -h localhost -p 5432 -U OPCP_user -d OPCP_db -F c -f test_backup.sql

# Voir les logs PostgreSQL
docker logs OPCP-postgres
```

## Variables d'Environnement

```bash
# Afficher DATABASE_URL (masqué)
echo $DATABASE_URL | sed 's/:.*@/:***@/'

# Définir temporairement DATABASE_URL
export DATABASE_URL="postgresql://user:pass@host:5432/db"

# Charger depuis .env
export $(cat .env | xargs)
```

## Maintenance

```bash
# Nettoyer les sauvegardes locales de plus de 30 jours
find ./backups -name "OPCP_backup_*.sql" -mtime +30 -delete

# Calculer l'espace utilisé par les sauvegardes locales
du -sh ./backups

# Calculer l'espace utilisé dans S3
aws s3 ls s3://ai-OPCP/ --recursive --summarize | grep "Total Size"

# Compter le nombre de sauvegardes dans S3
aws s3 ls s3://ai-OPCP/ --recursive | grep ".sql" | wc -l
```

## Sécurité

```bash
# Chiffrer une sauvegarde locale avec GPG
gpg --symmetric --cipher-algo AES256 backups/OPCP_backup_20260220_143000.sql

# Déchiffrer
gpg --decrypt backups/OPCP_backup_20260220_143000.sql.gpg > backup.sql

# Vérifier les permissions du bucket S3
aws s3api get-bucket-acl --bucket ai-OPCP

# Activer le versioning S3
aws s3api put-bucket-versioning --bucket ai-OPCP --versioning-configuration Status=Enabled
```

## Monitoring

```bash
# Vérifier la dernière sauvegarde locale
ls -lth ./backups | head -n 2

# Vérifier la dernière sauvegarde S3
aws s3 ls s3://ai-OPCP/ --recursive | sort | tail -n 1

# Alertes par email (exemple avec sendmail)
python scripts/backup_database.py && echo "Backup OK" | mail -s "OPCP Backup Success" admin@opcp-psmc.com || echo "Backup FAILED" | mail -s "OPCP Backup FAILED" admin@opcp-psmc.com
```
