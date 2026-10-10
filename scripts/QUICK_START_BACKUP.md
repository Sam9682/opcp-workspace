# Guide de Démarrage Rapide - Sauvegardes S3

## Installation en 5 minutes

### 1. Installer les dépendances
```bash
# PostgreSQL client
sudo apt-get install postgresql-client

# Python dependencies
pip install boto3

# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### 2. Configurer AWS
```bash
aws configure
```
Entrez vos credentials AWS :
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `eu-west-3` (Paris)
- Default output format: `json`

### 3. Créer et configurer le bucket S3
```bash
bash scripts/setup_s3_bucket.sh
```

### 4. Tester la sauvegarde
```bash
python scripts/backup_database.py
```

## Utilisation Quotidienne

### Créer une sauvegarde
```bash
python scripts/backup_database.py
```

### Lister les sauvegardes S3
```bash
python scripts/restore_from_s3.py list
```

### Restaurer depuis S3
```bash
# 1. Lister les sauvegardes disponibles
python scripts/restore_from_s3.py list

# 2. Restaurer une sauvegarde spécifique
python scripts/restore_from_s3.py restore 2026/02/20/OPCP_backup_20260220_143000.sql
```

## Automatisation avec Cron

```bash
# Éditer le crontab
crontab -e

# Ajouter cette ligne pour une sauvegarde quotidienne à 2h du matin
0 2 * * * cd /path/to/OPCP && /usr/bin/python3 scripts/backup_database.py >> /var/log/OPCP_backup.log 2>&1
```

## Vérification

### Vérifier que tout fonctionne
```bash
# 1. Créer une sauvegarde de test
python scripts/backup_database.py

# 2. Vérifier dans S3
aws s3 ls s3://ai-OPCP/ --recursive

# 3. Lister via le script
python scripts/restore_from_s3.py list
```

## Dépannage Rapide

### Erreur: NoCredentialsError
```bash
aws configure
```

### Erreur: Bucket does not exist
```bash
bash scripts/setup_s3_bucket.sh
```

### Erreur: pg_dump not found
```bash
sudo apt-get install postgresql-client
```

## Structure des Sauvegardes

```
s3://ai-OPCP/
├── 2026/
│   ├── 02/
│   │   └── 20/
│   │       └── OPCP_backup_20260220_143000.sql
│   └── 03/
│       └── ...
```

## Coûts Estimés

Pour ~10 GB de sauvegardes :
- Premier mois (STANDARD_IA) : ~0.13 USD
- Après 30 jours (GLACIER) : ~0.04 USD/mois
- Total annuel : ~0.50 USD

## Support

Documentation complète : `scripts/README_BACKUP.md`
