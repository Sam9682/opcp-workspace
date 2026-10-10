#!/usr/bin/env python3
"""
Script de sauvegarde de la base de données PostgreSQL OPCP
Sauvegarde locale et upload automatique vers S3
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def parse_database_url(database_url: str) -> dict:
    """Parse l'URL de la base de données pour extraire les paramètres de connexion"""
    parsed = urlparse(database_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/'),
        'username': parsed.username,
        'password': parsed.password
    }


def upload_to_s3(file_path: Path, bucket_name: str = "ai-OPCP") -> bool:
    """
    Upload le fichier de sauvegarde vers S3
    
    Args:
        file_path: Chemin du fichier à uploader
        bucket_name: Nom du bucket S3
        
    Returns:
        True si l'upload a réussi, False sinon
    """
    try:
        # Créer le client S3
        s3_client = boto3.client('s3')
        
        # Générer la clé S3 avec la date
        timestamp = datetime.now().strftime('%Y/%m/%d')
        s3_key = f"{timestamp}/{file_path.name}"
        
        print(f"\n☁️  Upload vers S3...")
        print(f"   Bucket: s3://{bucket_name}/{s3_key}")
        
        # Upload le fichier
        s3_client.upload_file(
            str(file_path),
            bucket_name,
            s3_key,
            ExtraArgs={
                'StorageClass': 'STANDARD_IA',  # Stockage peu fréquent, moins cher
                'ServerSideEncryption': 'AES256'  # Chiffrement côté serveur
            }
        )
        
        print(f"✅ Upload S3 réussi: s3://{bucket_name}/{s3_key}")
        return True
        
    except NoCredentialsError:
        print("❌ Erreur: Credentials AWS non trouvés")
        print("   Configurez AWS CLI avec: aws configure")
        return False
    except ClientError as e:
        print(f"❌ Erreur S3: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue lors de l'upload S3: {e}")
        return False


def create_backup(backup_dir: str = "./backups", retention_days: int = 30, upload_s3: bool = True, s3_bucket: str = "ai-OPCP") -> bool:
    """
    Crée une sauvegarde de la base de données PostgreSQL
    
    Args:
        backup_dir: Répertoire où stocker les sauvegardes locales
        retention_days: Nombre de jours de rétention des sauvegardes locales
        upload_s3: Si True, upload la sauvegarde vers S3
        s3_bucket: Nom du bucket S3
        
    Returns:
        True si la sauvegarde a réussi, False sinon
    """
    # Charger l'URL de la base de données depuis les variables d'environnement
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Erreur: DATABASE_URL n'est pas défini dans les variables d'environnement")
        return False
    
    # Parser l'URL de la base de données
    db_config = parse_database_url(database_url)
    
    # Créer le répertoire de sauvegarde s'il n'existe pas
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Générer le nom du fichier de sauvegarde avec timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_path / f"OPCP_backup_{timestamp}.sql"
    
    print(f"🔄 Démarrage de la sauvegarde de la base de données '{db_config['database']}'...")
    print(f"📁 Fichier de sauvegarde: {backup_file}")
    
    # Préparer la commande pg_dump
    env = os.environ.copy()
    env['PGPASSWORD'] = db_config['password']
    
    cmd = [
        'pg_dump',
        '-h', db_config['host'],
        '-p', str(db_config['port']),
        '-U', db_config['username'],
        '-d', db_config['database'],
        '-F', 'c',  # Format custom (compressé)
        '-f', str(backup_file)
    ]
    
    try:
        # Exécuter pg_dump
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Vérifier que le fichier a été créé
        if backup_file.exists():
            file_size = backup_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"✅ Sauvegarde locale réussie! Taille: {file_size_mb:.2f} MB")
            
            # Upload vers S3 si demandé
            s3_success = True
            if upload_s3:
                s3_success = upload_to_s3(backup_file, s3_bucket)
            
            # Nettoyer les anciennes sauvegardes locales
            cleanup_old_backups(backup_path, retention_days)
            
            return s3_success
        else:
            print("❌ Erreur: Le fichier de sauvegarde n'a pas été créé")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        print(f"Sortie d'erreur: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False


def cleanup_old_backups(backup_dir: Path, retention_days: int):
    """Supprime les sauvegardes plus anciennes que retention_days"""
    from datetime import timedelta
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0
    
    print(f"\n🧹 Nettoyage des sauvegardes de plus de {retention_days} jours...")
    
    for backup_file in backup_dir.glob("OPCP_backup_*.sql"):
        file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
        if file_time < cutoff_date:
            try:
                backup_file.unlink()
                deleted_count += 1
                print(f"   Supprimé: {backup_file.name}")
            except Exception as e:
                print(f"   ⚠️  Impossible de supprimer {backup_file.name}: {e}")
    
    if deleted_count > 0:
        print(f"✅ {deleted_count} ancienne(s) sauvegarde(s) supprimée(s)")
    else:
        print("✅ Aucune ancienne sauvegarde à supprimer")


def list_backups(backup_dir: str = "./backups"):
    """Liste toutes les sauvegardes disponibles"""
    backup_path = Path(backup_dir)
    
    if not backup_path.exists():
        print(f"📁 Le répertoire {backup_dir} n'existe pas encore")
        return
    
    backups = sorted(backup_path.glob("OPCP_backup_*.sql"), reverse=True)
    
    if not backups:
        print(f"📁 Aucune sauvegarde trouvée dans {backup_dir}")
        return
    
    print(f"\n📋 Sauvegardes disponibles dans {backup_dir}:")
    print("-" * 80)
    
    for backup in backups:
        file_size = backup.stat().st_size / (1024 * 1024)
        file_time = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"  {backup.name}")
        print(f"    Taille: {file_size:.2f} MB | Date: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("-" * 80)
    print(f"Total: {len(backups)} sauvegarde(s)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sauvegarde de la base de données OPCP")
    parser.add_argument(
        '--backup-dir',
        default='./backups',
        help='Répertoire de sauvegarde locale (défaut: ./backups)'
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=30,
        help='Nombre de jours de rétention locale (défaut: 30)'
    )
    parser.add_argument(
        '--no-s3',
        action='store_true',
        help='Ne pas uploader vers S3 (sauvegarde locale uniquement)'
    )
    parser.add_argument(
        '--s3-bucket',
        default='ai-OPCP',
        help='Nom du bucket S3 (défaut: ai-OPCP)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='Lister les sauvegardes locales existantes'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_backups(args.backup_dir)
    else:
        success = create_backup(
            args.backup_dir, 
            args.retention_days,
            upload_s3=not args.no_s3,
            s3_bucket=args.s3_bucket
        )
        sys.exit(0 if success else 1)
