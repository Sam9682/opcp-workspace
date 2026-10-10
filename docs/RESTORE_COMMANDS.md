# Commandes de Restauration Rapide

## Votre Backup OVH

- **Bucket**: `ai-OPCP`
- **Chemin**: `10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz`
- **Profil AWS**: `OVH-SWAUTOMORPH`
- **Application**: `~/deployments/admin/ai-OPCP`

## Option 1 : Script Automatisé (Recommandé)

```bash
cd ~/deployments/admin/ai-OPCP
./scripts/restore_from_ovh_quick.sh
```

Ce script va :
1. ⬇️ Télécharger le backup depuis OVH
2. 📦 Décompresser le fichier .gz
3. 🔧 Charger la configuration
4. 🔄 Restaurer la base de données

## Option 2 : Commande Unique

```bash
cd ~/deployments/admin/ai-OPCP && \
mkdir -p backups && \
aws s3 cp s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz backups/ --profile OVH-SWAUTOMORPH && \
gunzip -f backups/OPCP_backup_20260220_160349.sql.gz && \
export $(cat .env | grep -v '^#' | xargs) && \
python3 scripts/restore_database.py backups/OPCP_backup_20260220_160349.sql
```

## Option 3 : Étape par Étape

### 1. Télécharger le backup

```bash
cd ~/deployments/admin/ai-OPCP
mkdir -p backups
aws s3 cp s3://ai-OPCP/10.1.3.176/20260220_160349/OPCP_backup_20260220_160349.sql.gz \
  backups/ \
  --profile OVH-SWAUTOMORPH
```

### 2. Décompresser

```bash
gunzip -f backups/OPCP_backup_20260220_160349.sql.gz
```

### 3. Charger la configuration

```bash
export $(cat .env | grep -v '^#' | xargs)
```

### 4. Restaurer

```bash
python3 scripts/restore_database.py backups/OPCP_backup_20260220_160349.sql
```

## Vérification Rapide

Après la restauration, vérifiez que tout fonctionne :

```bash
# Vérifier la connexion à la base
export $(cat ~/deployments/admin/ai-OPCP/.env | grep -v '^#' | xargs)
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"

# Vérifier l'application
cd ~/deployments/admin/ai-OPCP
docker-compose ps

# Vérifier les logs
docker-compose logs -f --tail=50
```

## Dépannage Rapide

### Si AWS CLI ne trouve pas le profil

```bash
aws configure --profile OVH-SWAUTOMORPH
# Entrez vos credentials OVH
```

### Si DATABASE_URL n'est pas défini

```bash
cat ~/deployments/admin/ai-OPCP/.env | grep DATABASE_URL
```

### Si pg_restore n'est pas installé

```bash
sudo apt-get update
sudo apt-get install postgresql-client
```

## Notes Importantes

⚠️ **SAUVEGARDE PRÉVENTIVE** : Avant de restaurer, sauvegardez la base actuelle :

```bash
cd ~/deployments/admin/ai-OPCP
python3 scripts/backup_database_universal.py --s3-provider ovh --s3-bucket ai-OPCP
```

⚠️ **ARRÊT DE L'APPLICATION** : Arrêtez l'application pendant la restauration :

```bash
cd ~/deployments/admin/ai-OPCP
docker-compose down

# Restaurer...

docker-compose up -d
```

## Support

Pour plus de détails, consultez :
- Guide complet : `RESTORE_OVH_BACKUP_GUIDE.md`
- Documentation backup : `scripts/README_BACKUP.md`
