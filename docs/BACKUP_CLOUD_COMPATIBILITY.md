# Compatibilité Multi-Cloud pour les Sauvegardes OPCP

## Vue d'ensemble

Le système de sauvegarde OPCP est maintenant compatible avec plusieurs fournisseurs de stockage cloud :

✅ **AWS S3** (Amazon Web Services)  
✅ **OVH Object Storage** (compatible S3)  
✅ **Tout fournisseur compatible S3** (Scaleway, DigitalOcean Spaces, MinIO, etc.)

## Architecture

Les scripts universels utilisent l'API S3 standard via boto3, ce qui permet la compatibilité avec tous les fournisseurs de stockage objet compatibles S3.

### Scripts Disponibles

| Script | Description |
|--------|-------------|
| `backup_database_universal.py` | Sauvegarde avec support AWS S3 et OVH |
| `restore_from_s3_universal.py` | Restauration depuis AWS S3 ou OVH |
| `backup_database.py` | Version originale (AWS uniquement) |
| `restore_from_s3.py` | Version originale (AWS uniquement) |

## Configuration

### 1. AWS S3 (Configuration par défaut)

```bash
# Installer AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configurer les credentials
aws configure
# AWS Access Key ID: VOTRE_ACCESS_KEY
# AWS Secret Access Key: VOTRE_SECRET_KEY
# Default region: eu-west-3
# Default output format: json
```

Variables d'environnement (optionnel) :
```bash
# .env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-west-3
```

### 2. OVH Object Storage

#### Étape 1 : Créer un utilisateur S3 dans OVH

1. Connectez-vous à l'espace client OVH
2. Allez dans `Public Cloud` > `Object Storage`
3. Créez un conteneur S3 (ex: `OPCP-backups`)
4. Créez un utilisateur S3 et notez :
   - Access Key ID
   - Secret Access Key
   - Endpoint (ex: `https://s3.gra.io.cloud.ovh.net`)
   - Région (ex: `gra`, `sbg`, `bhs`)

#### Étape 2 : Configurer les variables d'environnement

Ajoutez dans votre fichier `.env` :

```bash
# OVH Object Storage Configuration
OVH_S3_ACCESS_KEY=your_ovh_access_key
OVH_S3_SECRET_KEY=your_ovh_secret_key
OVH_S3_ENDPOINT=https://s3.gra.io.cloud.ovh.net
OVH_S3_REGION=gra
```

Endpoints OVH disponibles :
- Gravelines (France) : `https://s3.gra.io.cloud.ovh.net`
- Strasbourg (France) : `https://s3.sbg.io.cloud.ovh.net`
- Beauharnois (Canada) : `https://s3.bhs.io.cloud.ovh.net`
- Warsaw (Pologne) : `https://s3.waw.io.cloud.ovh.net`
- Londres (UK) : `https://s3.uk.io.cloud.ovh.net`

### 3. Autres Fournisseurs S3-compatibles

Pour d'autres fournisseurs (Scaleway, DigitalOcean, MinIO, etc.), utilisez la même approche qu'OVH :

```bash
# Exemple pour Scaleway
OVH_S3_ACCESS_KEY=your_scaleway_access_key
OVH_S3_SECRET_KEY=your_scaleway_secret_key
OVH_S3_ENDPOINT=https://s3.fr-par.scw.cloud
OVH_S3_REGION=fr-par
```

## Utilisation

### Sauvegarde

#### Avec AWS S3 (par défaut)
```bash
python scripts/backup_database_universal.py
```

#### Avec OVH Object Storage
```bash
python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups
```

#### Options disponibles
```bash
# Sauvegarde locale uniquement (sans cloud)
python scripts/backup_database_universal.py --no-s3

# Changer le bucket
python scripts/backup_database_universal.py --s3-bucket mon-bucket --s3-provider ovh

# Changer la rétention locale
python scripts/backup_database_universal.py --retention-days 60

# Lister les sauvegardes locales
python scripts/backup_database_universal.py --list
```

### Restauration

#### Lister les sauvegardes

AWS S3 :
```bash
python scripts/restore_from_s3_universal.py --provider aws list
```

OVH Object Storage :
```bash
python scripts/restore_from_s3_universal.py --provider ovh --bucket OPCP-backups list
```

Filtrer par date :
```bash
python scripts/restore_from_s3_universal.py --provider ovh list --prefix 2026/02/
```

#### Télécharger une sauvegarde

```bash
# Depuis OVH
python scripts/restore_from_s3_universal.py --provider ovh download 2026/02/28/OPCP_backup_20260228_143000.sql

# Depuis AWS
python scripts/restore_from_s3_universal.py --provider aws download 2026/02/28/OPCP_backup_20260228_143000.sql
```

#### Restaurer la base de données

```bash
# Depuis OVH (téléchargement + restauration automatique)
python scripts/restore_from_s3_universal.py --provider ovh --bucket OPCP-backups restore 2026/02/28/OPCP_backup_20260228_143000.sql

# Depuis AWS
python scripts/restore_from_s3_universal.py --provider aws restore 2026/02/28/OPCP_backup_20260228_143000.sql
```

## Automatisation avec Cron

### Sauvegarde quotidienne vers OVH

```bash
crontab -e
```

Ajouter :
```cron
# Sauvegarde quotidienne à 2h du matin vers OVH
0 2 * * * cd /path/to/OPCP && /usr/bin/python3 scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups >> /var/log/OPCP_backup.log 2>&1
```

### Sauvegarde vers plusieurs clouds (redondance)

```bash
#!/bin/bash
# backup_multi_cloud.sh

# Sauvegarde vers AWS
python scripts/backup_database_universal.py --s3-provider aws --s3-bucket ai-OPCP

# Sauvegarde vers OVH
python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups
```

Cron :
```cron
0 2 * * * /path/to/backup_multi_cloud.sh >> /var/log/OPCP_backup.log 2>&1
```

## Comparaison des Fournisseurs

### AWS S3

**Avantages :**
- ✅ Service mature et fiable
- ✅ Nombreuses options de stockage (STANDARD, STANDARD_IA, GLACIER)
- ✅ Lifecycle policies avancées
- ✅ Intégration native avec AWS

**Inconvénients :**
- ❌ Coûts potentiellement plus élevés
- ❌ Complexité de la facturation

**Coûts estimés (région eu-west-3) :**
- STANDARD_IA : ~0.0125 USD/GB/mois
- GLACIER : ~0.004 USD/GB/mois
- Exemple : 10 GB ≈ 0.13 USD/mois

### OVH Object Storage

**Avantages :**
- ✅ Prix compétitifs
- ✅ Données hébergées en Europe (RGPD)
- ✅ Support français
- ✅ Compatible S3 (facile à migrer)

**Inconvénients :**
- ❌ Moins d'options de stockage que AWS
- ❌ Pas de Glacier équivalent

**Coûts estimés (région GRA) :**
- Stockage : ~0.01 EUR/GB/mois
- Exemple : 10 GB ≈ 0.10 EUR/mois (~0.11 USD/mois)

### Recommandations

| Cas d'usage | Recommandation |
|-------------|----------------|
| **Hébergement en Europe** | OVH (conformité RGPD) |
| **Budget limité** | OVH (moins cher) |
| **Infrastructure AWS existante** | AWS S3 |
| **Archivage long terme** | AWS S3 + Glacier |
| **Redondance maximale** | AWS + OVH (multi-cloud) |

## Sécurité

### Chiffrement

Les deux fournisseurs supportent :
- ✅ Chiffrement côté serveur (AES256)
- ✅ Chiffrement en transit (HTTPS/TLS)

### Bonnes pratiques

1. **Ne jamais commiter les credentials dans Git**
   ```bash
   # .gitignore
   .env
   *.key
   ```

2. **Utiliser des variables d'environnement**
   ```bash
   # Charger depuis .env
   export $(cat .env | xargs)
   ```

3. **Permissions minimales**
   - AWS : Utiliser IAM avec permissions limitées
   - OVH : Créer un utilisateur S3 dédié aux sauvegardes

4. **Tester régulièrement la restauration**
   ```bash
   # Test mensuel recommandé
   python scripts/restore_from_s3_universal.py --provider ovh list
   ```

5. **Activer le versioning** (si disponible)
   - Protection contre les suppressions accidentelles
   - Récupération de versions antérieures

## Migration entre Fournisseurs

### De AWS vers OVH

```bash
# 1. Lister les sauvegardes AWS
python scripts/restore_from_s3_universal.py --provider aws list

# 2. Télécharger une sauvegarde
python scripts/restore_from_s3_universal.py --provider aws download 2026/02/28/OPCP_backup_20260228_143000.sql

# 3. Uploader vers OVH (utiliser AWS CLI ou script personnalisé)
# Ou simplement créer une nouvelle sauvegarde vers OVH
python scripts/backup_database_universal.py --s3-provider ovh --s3-bucket OPCP-backups
```

### Synchronisation entre clouds

Pour maintenir des sauvegardes sur les deux clouds :

```bash
#!/bin/bash
# sync_backups.sh

# Télécharger depuis AWS
python scripts/restore_from_s3_universal.py --provider aws download $BACKUP_KEY

# Uploader vers OVH (nécessite un script personnalisé ou AWS CLI)
# TODO: Implémenter la synchronisation bidirectionnelle
```

## Dépannage

### Erreur : NoCredentialsError (OVH)

```bash
# Vérifier que les variables sont définies
echo $OVH_S3_ACCESS_KEY
echo $OVH_S3_SECRET_KEY

# Les définir si nécessaire
export OVH_S3_ACCESS_KEY=your_key
export OVH_S3_SECRET_KEY=your_secret
```

### Erreur : EndpointConnectionError

```bash
# Vérifier l'endpoint
echo $OVH_S3_ENDPOINT

# Tester la connectivité
curl -I https://s3.gra.io.cloud.ovh.net
```

### Erreur : Bucket does not exist

```bash
# Créer le bucket via l'interface OVH ou AWS CLI
aws s3 mb s3://OPCP-backups --endpoint-url https://s3.gra.io.cloud.ovh.net
```

### Tester la configuration

```bash
# Test complet
python scripts/test_backup_setup.py --provider ovh
```

## Support et Documentation

### AWS S3
- Documentation : https://docs.aws.amazon.com/s3/
- boto3 : https://boto3.amazonaws.com/v1/documentation/api/latest/index.html

### OVH Object Storage
- Documentation : https://docs.ovh.com/fr/storage/object-storage/
- Guide S3 : https://docs.ovh.com/fr/storage/s3/getting-started-with-s3/

### PostgreSQL
- pg_dump : https://www.postgresql.org/docs/current/app-pgdump.html
- pg_restore : https://www.postgresql.org/docs/current/app-pgrestore.html

## Conclusion

Le système de sauvegarde OPCP est maintenant **multi-cloud** et offre :

✅ Flexibilité de choix du fournisseur  
✅ Compatibilité avec tout service S3  
✅ Migration facile entre fournisseurs  
✅ Redondance possible (multi-cloud)  
✅ Conformité RGPD (avec OVH Europe)  
✅ Optimisation des coûts  

Choisissez le fournisseur qui correspond le mieux à vos besoins en termes de coûts, localisation des données, et infrastructure existante.
