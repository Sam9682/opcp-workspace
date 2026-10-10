# Sauvegarde et Restauration de la Base de Données OPCP

Ce dossier contient les scripts pour sauvegarder et restaurer la base de données PostgreSQL OPCP, avec support multi-cloud (AWS S3 et OVH Object Storage).

## Compatibilité Cloud

✅ **AWS S3** - Stockage objet Amazon (par défaut)  
✅ **OVH Object Storage** - Stockage objet OVH compatible S3  
✅ **Tout fournisseur S3-compatible** - Scaleway, DigitalOcean Spaces, MinIO, etc.

Pour plus de détails sur la compatibilité multi-cloud, consultez [BACKUP_CLOUD_COMPATIBILITY.md](../BACKUP_CLOUD_COMPATIBILITY.md)

## Scripts Disponibles

### Scripts Universels (Multi-Cloud)
- `backup_database_universal.py` - Sauvegarde avec support AWS et OVH
- `restore_from_s3_universal.py` - Restauration depuis AWS ou OVH

### Scripts Originaux (AWS uniquement)
- `backup_database.py` - Sauvegarde AWS S3 uniquement
- `restore_from_s3.py` - Restauration AWS S3 uniquement

## Prérequis

- PostgreSQL client tools (`pg_dump` et `pg_restore`) installés
- Variable d'environnement `DATABASE_URL` configurée
- AWS CLI configuré avec les credentials appropriés (pour S3)
- Python packages: `boto3`

## Installation

### PostgreSQL Client Tools

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install postgresql-client
```

#### macOS
```bash
brew install postgresql
```

### Configuration Cloud

#### Option 1: AWS S3 (par défaut)

```bash
# Installer AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configurer AWS
aws configure
# Entrez: AWS Access Key ID, Secret Access Key, Region (ex: eu-west-3)

# Installer boto3
pip install boto3
```

#### Option 2: OVH Object Storage

```bash
# Installer boto3
pip install boto3

# Configurer les variables d'environnement dans .env
OVH_S3_ACCESS_KEY=your_ovh_access_key
OVH_S3_SECRET_KEY=your_ovh_secret_key
OVH_S3_ENDPOINT=https://s3.gra.io.cloud.ovh.net
OVH_S3_REGION=gra
```

Pour créer un utilisateur S3 OVH :
1. Connectez-vous à l'espace client OVH
2. Allez dans `Public Cloud` > `Object Storage`
3. Créez un conteneur S3
4. Créez un utilisateur S3 et notez les credentials

## Sauvegarde de la Base de Données

### Sauvegarde avec AWS S3 (par défaut)
```bash
# Utiliser le script universel
python scripts/backup_database_universal.py

# Ou le script original AWS uniquement
python scripts/backup_database.py
```

### Sauvegarde avec OVH Object Storage
```bash
python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups
```

Cette commande va :
1. Créer une sauvegarde locale dans `./backups/`
2. Uploader automatiquement vers le cloud : `bucket/YYYY/MM/DD/OPCP_backup_YYYYMMDD_HHMMSS.sql`
3. Nettoyer les anciennes sauvegardes locales (30 jours)

### Options disponibles
```bash
# Sauvegarde locale uniquement (sans cloud)
python scripts/backup_database_universal.py --no-s3

# Utiliser un bucket différent
python scripts/backup_database_universal.py --s3-bucket mon-autre-bucket --s3-provider ovh

# Changer la rétention locale
python scripts/backup_database_universal.py --retention-days 60

# Lister les sauvegardes locales
python scripts/backup_database_universal.py --list
```

## Gestion des Sauvegardes Cloud

### Lister les sauvegardes

AWS S3:
```bash
# Script universel
python scripts/restore_from_s3_universal.py --provider aws list

# Script original
python scripts/restore_from_s3.py list
```

OVH Object Storage:
```bash
python scripts/restore_from_s3_universal.py --provider ovh --bucket OPCP-backups list
```

Filtrer par date:
```bash
# AWS
python scripts/restore_from_s3_universal.py --provider aws list --prefix 2026/02/

# OVH
python scripts/restore_from_s3_universal.py --provider ovh list --prefix 2026/02/
```

### Télécharger une sauvegarde depuis le cloud

AWS:
```bash
python scripts/restore_from_s3_universal.py --provider aws download 2026/02/20/OPCP_backup_20260220_143000.sql
```

OVH:
```bash
python scripts/restore_from_s3_universal.py --provider ovh download 2026/02/20/OPCP_backup_20260220_143000.sql
```

## Restauration de la Base de Données

### Depuis une sauvegarde locale
```bash
python scripts/restore_database.py backups/OPCP_backup_20260220_143000.sql
```

### Depuis AWS S3 (téléchargement + restauration automatique)
```bash
# Script universel
python scripts/restore_from_s3_universal.py --provider aws restore 2026/02/20/OPCP_backup_20260220_143000.sql

# Script original
python scripts/restore_from_s3.py restore 2026/02/20/OPCP_backup_20260220_143000.sql
```

### Depuis OVH Object Storage
```bash
python scripts/restore_from_s3_universal.py --provider ovh --bucket OPCP-backups restore 2026/02/20/OPCP_backup_20260220_143000.sql
```

⚠️ **ATTENTION**: La restauration écrasera toutes les données actuelles de la base de données !

## Organisation des Sauvegardes Cloud

Les sauvegardes sont organisées par date dans le stockage cloud :

AWS S3:
```
s3://ai-OPCP/
├── 2026/
│   ├── 02/
│   │   ├── 20/
│   │   │   ├── OPCP_backup_20260220_020000.sql
│   │   │   └── OPCP_backup_20260220_143000.sql
│   │   └── 21/
│   │       └── OPCP_backup_20260221_020000.sql
│   └── 03/
│       └── ...
```

OVH Object Storage:
```
OPCP-backups/
├── 2026/
│   ├── 02/
│   │   ├── 20/
│   │   │   ├── OPCP_backup_20260220_020000.sql
│   │   │   └── OPCP_backup_20260220_143000.sql
│   │   └── 21/
│   │       └── OPCP_backup_20260221_020000.sql
│   └── 03/
│       └── ...
```

## Sauvegarde Automatique avec Cron

Pour automatiser les sauvegardes quotidiennes avec upload cloud :

### Vers AWS S3
```bash
# Éditer le crontab
crontab -e

# Ajouter cette ligne pour une sauvegarde quotidienne à 2h du matin
0 2 * * * cd /path/to/OPCP && /usr/bin/python3 scripts/backup_database_universal.py --s3-provider aws >> /var/log/OPCP_backup.log 2>&1
```

### Vers OVH Object Storage
```bash
# Éditer le crontab
crontab -e

# Ajouter cette ligne pour une sauvegarde quotidienne à 2h du matin
0 2 * * * cd /path/to/OPCP && /usr/bin/python3 scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups >> /var/log/OPCP_backup.log 2>&1
```

### Redondance Multi-Cloud
Pour sauvegarder vers AWS ET OVH simultanément :

```bash
#!/bin/bash
# backup_multi_cloud.sh

# Sauvegarde vers AWS
python scripts/backup_database_universal.py --s3-provider aws --s3-bucket ai-OPCP

# Sauvegarde vers OVH
python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups
```

Cron:
```bash
0 2 * * * /path/to/backup_multi_cloud.sh >> /var/log/OPCP_backup.log 2>&1
```

## Configuration Cloud

### AWS S3

#### Permissions IAM requises

Le compte AWS doit avoir les permissions suivantes sur le bucket `ai-OPCP` :

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::ai-OPCP",
        "arn:aws:s3:::ai-OPCP/*"
      ]
    }
  ]
}
```

#### Lifecycle Policy S3 (optionnel)

Pour gérer automatiquement la rétention des sauvegardes dans S3 :

```json
{
  "Rules": [
    {
      "Id": "DeleteOldBackups",
      "Status": "Enabled",
      "Prefix": "",
      "Expiration": {
        "Days": 90
      }
    },
    {
      "Id": "TransitionToGlacier",
      "Status": "Enabled",
      "Prefix": "",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

### OVH Object Storage

#### Configuration du bucket

1. Créer un conteneur S3 dans l'espace client OVH
2. Créer un utilisateur S3 avec les permissions :
   - `s3:PutObject`
   - `s3:GetObject`
   - `s3:ListBucket`
   - `s3:DeleteObject`

#### Endpoints disponibles

- Gravelines (France) : `https://s3.gra.io.cloud.ovh.net`
- Strasbourg (France) : `https://s3.sbg.io.cloud.ovh.net`
- Beauharnois (Canada) : `https://s3.bhs.io.cloud.ovh.net`
- Warsaw (Pologne) : `https://s3.waw.io.cloud.ovh.net`
- Londres (UK) : `https://s3.uk.io.cloud.ovh.net`

#### Politique de rétention

OVH Object Storage ne supporte pas les lifecycle policies comme AWS. Utilisez un script cron pour nettoyer les anciennes sauvegardes :

```bash
# cleanup_old_backups_ovh.sh
# TODO: Implémenter le nettoyage automatique pour OVH
```

## Format des Sauvegardes

Les sauvegardes sont créées au format PostgreSQL custom (`-F c`), qui offre :
- Compression automatique
- Chiffrement côté serveur (AES256) dans le cloud
- Stockage optimisé (STANDARD_IA pour AWS, STANDARD pour OVH)
- Restauration sélective possible

## Comparaison des Fournisseurs

### AWS S3
- ✅ Service mature et fiable
- ✅ Nombreuses options de stockage (STANDARD, STANDARD_IA, GLACIER)
- ✅ Lifecycle policies avancées
- ❌ Coûts potentiellement plus élevés
- Coût estimé : ~0.13 USD/mois pour 10 GB

### OVH Object Storage
- ✅ Prix compétitifs (~0.10 EUR/mois pour 10 GB)
- ✅ Données hébergées en Europe (RGPD)
- ✅ Support français
- ✅ Compatible S3 (facile à migrer)
- ❌ Moins d'options de stockage que AWS

Voir [BACKUP_CLOUD_COMPATIBILITY.md](../BACKUP_CLOUD_COMPATIBILITY.md) pour plus de détails.

## Docker

Si vous utilisez Docker, vous pouvez exécuter les scripts depuis le conteneur :

```bash
# Sauvegarde vers AWS
docker exec -it <container_name> python scripts/backup_database_universal.py --s3-provider aws

# Sauvegarde vers OVH
docker exec -it <container_name> python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups

# Lister les sauvegardes AWS
docker exec -it <container_name> python scripts/restore_from_s3_universal.py --provider aws list

# Lister les sauvegardes OVH
docker exec -it <container_name> python scripts/restore_from_s3_universal.py --provider ovh list

# Restaurer depuis AWS
docker exec -it <container_name> python scripts/restore_from_s3_universal.py --provider aws restore 2026/02/20/OPCP_backup_20260220_143000.sql

# Restaurer depuis OVH
docker exec -it <container_name> python scripts/restore_from_s3_universal.py --provider ovh restore 2026/02/20/OPCP_backup_20260220_143000.sql
```

## Intégration avec l'Application

Vous pouvez créer des endpoints API pour gérer les sauvegardes :

```python
# Dans app/admin/router.py
from fastapi import BackgroundTasks

@router.post("/backup-database")
async def trigger_backup(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin_user)
):
    """Déclenche une sauvegarde de la base de données"""
    def run_backup():
        import subprocess
        subprocess.run(["python", "scripts/backup_database.py"])
    
    background_tasks.add_task(run_backup)
    return {"message": "Sauvegarde démarrée en arrière-plan"}

@router.get("/backups/s3")
async def list_s3_backups(current_user: User = Depends(get_current_admin_user)):
    """Liste les sauvegardes disponibles dans S3"""
    import boto3
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket='ai-OPCP')
    backups = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.sql')]
    return {"backups": backups}
```

## Dépannage

### Erreur: pg_dump: command not found
Installez les outils client PostgreSQL (voir section Installation).

### Erreur: NoCredentialsError (AWS)
Configurez AWS CLI :
```bash
aws configure
```

### Erreur: NoCredentialsError (OVH)
Vérifiez les variables d'environnement :
```bash
echo $OVH_S3_ACCESS_KEY
echo $OVH_S3_SECRET_KEY
```

Définissez-les si nécessaire :
```bash
export OVH_S3_ACCESS_KEY=your_key
export OVH_S3_SECRET_KEY=your_secret
```

### Erreur: Access Denied
Vérifiez que votre compte a les permissions nécessaires sur le bucket.

### Le bucket n'existe pas (AWS)
Créez le bucket :
```bash
aws s3 mb s3://ai-OPCP --region eu-west-3
```

### Le bucket n'existe pas (OVH)
Créez le conteneur via l'espace client OVH ou avec AWS CLI :
```bash
aws s3 mb s3://OPCP-backups --endpoint-url https://s3.gra.io.cloud.ovh.net
```

### Erreur: EndpointConnectionError (OVH)
Vérifiez l'endpoint :
```bash
echo $OVH_S3_ENDPOINT
curl -I https://s3.gra.io.cloud.ovh.net
```

## Sécurité

- Les sauvegardes cloud sont chiffrées avec AES256
- Ne commitez jamais les credentials dans Git
- Utilisez IAM roles pour les instances EC2 (AWS)
- Utilisez des utilisateurs S3 dédiés (OVH)
- Activez le versioning si disponible
- Testez régulièrement la restauration

## Coûts Cloud

### AWS S3
Avec STANDARD_IA et transition vers Glacier après 30 jours :
- Stockage STANDARD_IA : ~0.0125 USD/GB/mois
- Stockage GLACIER : ~0.004 USD/GB/mois
- Exemple : 10 GB de sauvegardes ≈ 0.13 USD/mois

### OVH Object Storage
- Stockage STANDARD : ~0.01 EUR/GB/mois
- Exemple : 10 GB de sauvegardes ≈ 0.10 EUR/mois (~0.11 USD/mois)

**Recommandation** : OVH est ~15% moins cher et héberge les données en Europe (RGPD).

## Support

Documentation :
- PostgreSQL: https://www.postgresql.org/docs/current/app-pgdump.html
- AWS S3: https://docs.aws.amazon.com/s3/
- OVH Object Storage: https://docs.ovh.com/fr/storage/object-storage/
- boto3: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- Guide complet multi-cloud: [BACKUP_CLOUD_COMPATIBILITY.md](../BACKUP_CLOUD_COMPATIBILITY.md)
