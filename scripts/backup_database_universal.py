#!/usr/bin/env python3
"""
Script de sauvegarde de la base de données PostgreSQL OPCP
Compatible avec AWS S3 et OVH Object Storage (S3-compatible)
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config


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


def get_s3_client(provider: str = "aws"):
    """
    Crée un client S3 compatible avec différents fournisseurs
    
    Args:
        provider: "aws" ou "ovh"
        
    Returns:
        Client boto3 configuré
    """
    if provider.lower() == "ovh":
        # Configuration pour OVH Object Storage
        endpoint_url = os.getenv('OVH_S3_ENDPOINT', 'https://s3.gra.io.cloud.ovh.net')
        region = os.getenv('OVH_S3_REGION', 'gra')
        access_key = os.getenv('OVH_S3_ACCESS_KEY')
        secret_key = os.getenv('OVH_S3_SECRET_KEY')
        
        if not access_key or not secret_key:
            raise ValueError(
                "OVH credentials manquants. Définissez OVH_S3_ACCESS_KEY et OVH_S3_SECRET_KEY"
            )
        
        return boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version='s3v4')
        )
    else:
        # Configuration AWS standard
        return boto3.client('s3')


def upload_to_s3(
    file_path: Path, 
    bucket_name: str = "ai-OPCP",
    provider: str = "aws"
) -> bool:
    """
    Upload le fichier de sauvegarde vers S3 (AWS ou OVH)
    
    Args:
        file_path: Chemin du fichier à uploader
        bucket_name: Nom du bucket S3
        provider: "aws" ou "ovh"
        
    Returns:
        True si l'upload a réussi, False sinon
    """
    try:
        # Créer le client S3
        s3_client = get_s3_client(provider)
        
        # Générer la clé S3 avec la date
        timestamp = datetime.now().strftime('%Y/%m/%d')
        s3_key = f"{timestamp}/{file_path.name}"
        
        provider_name = "OVH Object Storage" if provider.lower() == "ovh" else "AWS S3"
        print(f"\n☁️  Upload vers {provider_name}...")
        print(f"   Bucket: {bucket_name}/{s3_key}")
        
        # Préparer les arguments d'upload
        extra_args = {
            'ServerSideEncryption': 'AES256'  # Chiffrement côté serveur
        }
        
        # AWS supporte STANDARD_IA, OVH utilise STANDARD
        if provider.lower() == "aws":
            extra_args['StorageClass'] = 'STANDARD_IA'
        
        # Upload le fichier
        s3_client.upload_file(
            str(file_path),
            bucket_name,
            s3_key,
            ExtraArgs=extra_args
        )
        
        print(f"✅ Upload {provider_name} réussi: {bucket_name}/{s3_key}")
        return True
        
    except NoCredentialsError:
        print(f"❌ Erreur: Credentials {provider.upper()} non trouvés")
        if provider.lower() == "aws":
            print("   Configurez AWS CLI avec: aws configure")
        else:
            print("   Définissez: OVH_S3_ACCESS_KEY et OVH_S3_SECRET_KEY")
        return False
    except ClientError as e:
        print(f"❌ Erreur S3: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue lors de l'upload S3: {e}")
        return False


def create_backup(
    backup_dir: str = "./backups",
    retention_days: int = 30,
    upload_s3: bool = True,
    s3_bucket: str = "ai-OPCP",
    s3_provider: str = "aws"
) -> bool:
    """
    Crée une sauvegarde de la base de données PostgreSQL
    
    Args:
        backup_dir: Répertoire où stocker les sauvegardes locales
        retention_days: Nombre de jours de rétention des sauvegardes locales
        upload_s3: Si True, upload la sauvegarde vers S3
        s3_bucket: Nom du bucket S3
        s3_provider: "aws" ou "ovh"
        
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
                s3_success = upload_to_s3(backup_file, s3_bucket, s3_provider)
            
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
    
    parser = argparse.ArgumentParser(
        description="Sauvegarde de la base de données OPCP (AWS S3 ou OVH Object Storage)"
    )
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
        '--s3-provider',
        choices=['aws', 'ovh'],
        default='aws',
        help='Fournisseur S3: aws ou ovh (défaut: aws)'
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
            s3_bucket=args.s3_bucket,
            s3_provider=args.s3_provider
        )
        sys.exit(0 if success else 1)
