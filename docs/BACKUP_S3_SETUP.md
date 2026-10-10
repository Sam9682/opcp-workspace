# Système de Sauvegarde S3 pour OPCP

## Vue d'ensemble

Système complet de sauvegarde automatique de la base de données PostgreSQL avec stockage dans AWS S3.

### Fonctionnalités

✅ Sauvegarde automatique vers S3 (bucket: `ai-OPCP`)  
✅ Organisation par date : `s3://ai-OPCP/YYYY/MM/DD/`  
✅ Chiffrement AES256 côté serveur  
✅ Compression automatique (format PostgreSQL custom)  
✅ Rétention configurable (locale et S3)  
✅ Restauration simple depuis S3  
✅ Scripts de test et configuration  

## Démarrage Rapide

### 1. Installation
```bash
# Installer les dépendances
pip install -r requirements.txt
sudo apt-get install postgresql-client

# Installer et configurer AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws configure
```

### 2. Configuration du bucket S3
```bash
bash scripts/setup_s3_bucket.sh
```

### 3. Test de la configuration
```bash
python scripts/test_backup_setup.py
```

### 4. Première sauvegarde
```bash
python scripts/backup_database.py
```

## Scripts Disponibles

| Script | Description |
|--------|-------------|
| `backup_database.py` | Crée une sauvegarde et l'upload vers S3 |
| `restore_database.py` | Restaure depuis une sauvegarde locale |
| `restore_from_s3.py` | Gère les sauvegardes S3 (list/download/restore) |
| `setup_s3_bucket.sh` | Configure le bucket S3 avec les bonnes politiques |
| `test_backup_setup.py` | Vérifie que tout est correctement configuré |

## Utilisation

### Créer une sauvegarde
```bash
# Sauvegarde avec upload S3 (par défaut)
python scripts/backup_database.py

# Sauvegarde locale uniquement
python scripts/backup_database.py --no-s3

# Bucket S3 personnalisé
python scripts/backup_database.py --s3-bucket mon-bucket
```

### Lister les sauvegardes
```bash
# Sauvegardes locales
python scripts/backup_database.py --list

# Sauvegardes S3
python scripts/restore_from_s3.py list

# Filtrer par date
python scripts/restore_from_s3.py list --prefix 2026/02/
```

### Restaurer une sauvegarde
```bash
# Depuis S3 (téléchargement + restauration automatique)
python scripts/restore_from_s3.py restore 2026/02/20/OPCP_backup_20260220_143000.sql

# Depuis un fichier local
python scripts/restore_database.py backups/OPCP_backup_20260220_143000.sql
```

## Automatisation

### Sauvegarde quotidienne avec cron
```bash
crontab -e
```

Ajouter :
```cron
# Sauvegarde quotidienne à 2h du matin
0 2 * * * cd /path/to/OPCP && /usr/bin/python3 scripts/backup_database.py >> /var/log/OPCP_backup.log 2>&1
```

### Intégration Docker
```bash
# Depuis l'hôte
docker exec -it OPCP-container python scripts/backup_database.py

# Ou ajouter au Dockerfile
RUN echo "0 2 * * * python /app/scripts/backup_database.py" | crontab -
```

## Structure S3

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

## Configuration AWS

### Permissions IAM requises
Voir `scripts/iam-policy-example.json` pour la politique IAM complète.

### Lifecycle Policy
- Transition vers Glacier après 30 jours
- Suppression automatique après 365 jours
- Configurable via `scripts/setup_s3_bucket.sh`

## Sécurité

- ✅ Chiffrement AES256 côté serveur
- ✅ Versioning activé sur le bucket
- ✅ Accès public bloqué
- ✅ Credentials AWS non stockés dans le code
- ✅ Stockage STANDARD_IA pour réduire les coûts

## Coûts Estimés

Pour ~10 GB de sauvegardes :
- Stockage STANDARD_IA : ~0.13 USD/mois
- Après transition Glacier : ~0.04 USD/mois
- **Total annuel : ~0.50 USD**

## Documentation Complète

- 📖 Guide complet : `scripts/README_BACKUP.md`
- 🚀 Démarrage rapide : `scripts/QUICK_START_BACKUP.md`
- 🔧 Politique IAM : `scripts/iam-policy-example.json`

## Dépannage

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

### Tester la configuration
```bash
python scripts/test_backup_setup.py
```

## Support

Pour toute question :
1. Consultez `scripts/README_BACKUP.md`
2. Exécutez `python scripts/test_backup_setup.py`
3. Vérifiez les logs : `/var/log/OPCP_backup.log`

---

**Note** : Les sauvegardes sont critiques pour la continuité de service. Testez régulièrement la restauration !
