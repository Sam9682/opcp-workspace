#!/usr/bin/env python3
"""
Script de restauration de la base de données depuis S3
Compatible avec AWS S3 et OVH Object Storage
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.client import Config


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


def list_s3_backups(bucket_name: str = "ai-OPCP", prefix: str = "", provider: str = "aws"):
    """
    Liste les sauvegardes disponibles dans S3
    
    Args:
        bucket_name: Nom du bucket S3
        prefix: Préfixe pour filtrer (ex: "2026/02/")
        provider: "aws" ou "ovh"
    """
    try:
        s3_client = get_s3_client(provider)
        
        provider_name = "OVH Object Storage" if provider.lower() == "ovh" else "AWS S3"
        print(f"\n📋 Sauvegardes disponibles dans {provider_name} ({bucket_name})")
        print("-" * 100)
        
        # Lister les objets
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        backups = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].endswith('.sql'):
                        backups.append(obj)
        
        if not backups:
            print(f"Aucune sauvegarde trouvée dans {bucket_name}/{prefix}")
            return []
        
        # Trier par date (plus récent en premier)
        backups.sort(key=lambda x: x['LastModified'], reverse=True)
        
        for i, backup in enumerate(backups, 1):
            size_mb = backup['Size'] / (1024 * 1024)
            modified = backup['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"{i}. {bucket_name}/{backup['Key']}")
            print(f"   Taille: {size_mb:.2f} MB | Date: {modified}")
        
        print("-" * 100)
        print(f"Total: {len(backups)} sauvegarde(s)")
        
        return backups
        
    except NoCredentialsError:
        print(f"❌ Erreur: Credentials {provider.upper()} non trouvés")
        if provider.lower() == "aws":
            print("   Configurez AWS CLI avec: aws configure")
        else:
            print("   Définissez: OVH_S3_ACCESS_KEY et OVH_S3_SECRET_KEY")
        return []
    except ClientError as e:
        print(f"❌ Erreur S3: {e}")
        return []
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return []


def download_from_s3(
    s3_key: str,
    bucket_name: str = "ai-OPCP",
    local_dir: str = "./backups",
    provider: str = "aws"
) -> Path:
    """
    Télécharge une sauvegarde depuis S3
    
    Args:
        s3_key: Clé S3 du fichier (ex: "2026/02/20/OPCP_backup_20260220_143000.sql")
        bucket_name: Nom du bucket S3
        local_dir: Répertoire local de destination
        provider: "aws" ou "ovh"
        
    Returns:
        Path du fichier téléchargé ou None en cas d'erreur
    """
    try:
        s3_client = get_s3_client(provider)
        
        # Créer le répertoire local
        local_path = Path(local_dir)
        local_path.mkdir(parents=True, exist_ok=True)
        
        # Nom du fichier local
        filename = Path(s3_key).name
        local_file = local_path / filename
        
        provider_name = "OVH Object Storage" if provider.lower() == "ovh" else "AWS S3"
        print(f"\n⬇️  Téléchargement depuis {provider_name}...")
        print(f"   Source: {bucket_name}/{s3_key}")
        print(f"   Destination: {local_file}")
        
        # Télécharger le fichier
        s3_client.download_file(bucket_name, s3_key, str(local_file))
        
        file_size_mb = local_file.stat().st_size / (1024 * 1024)
        print(f"✅ Téléchargement réussi! Taille: {file_size_mb:.2f} MB")
        
        return local_file
        
    except NoCredentialsError:
        print(f"❌ Erreur: Credentials {provider.upper()} non trouvés")
        return None
    except ClientError as e:
        print(f"❌ Erreur S3: {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return None


def restore_from_s3(s3_key: str, bucket_name: str = "ai-OPCP", provider: str = "aws"):
    """
    Télécharge et restaure une sauvegarde depuis S3
    
    Args:
        s3_key: Clé S3 du fichier à restaurer
        bucket_name: Nom du bucket S3
        provider: "aws" ou "ovh"
    """
    # Télécharger le fichier
    local_file = download_from_s3(s3_key, bucket_name, provider=provider)
    
    if not local_file:
        print("❌ Échec du téléchargement")
        return False
    
    # Importer le script de restauration
    from restore_database import restore_backup
    
    # Restaurer la base de données
    success = restore_backup(str(local_file))
    
    # Optionnel: supprimer le fichier local après restauration
    if success:
        try:
            local_file.unlink()
            print(f"🧹 Fichier temporaire supprimé: {local_file}")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer le fichier temporaire: {e}")
    
    return success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Gestion des sauvegardes S3 OPCP (AWS ou OVH)"
    )
    parser.add_argument(
        '--bucket',
        default='ai-OPCP',
        help='Nom du bucket S3 (défaut: ai-OPCP)'
    )
    parser.add_argument(
        '--provider',
        choices=['aws', 'ovh'],
        default='aws',
        help='Fournisseur S3: aws ou ovh (défaut: aws)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
    
    # Commande list
    list_parser = subparsers.add_parser('list', help='Lister les sauvegardes S3')
    list_parser.add_argument(
        '--prefix',
        default='',
        help='Préfixe pour filtrer (ex: 2026/02/)'
    )
    
    # Commande download
    download_parser = subparsers.add_parser('download', help='Télécharger une sauvegarde')
    download_parser.add_argument(
        's3_key',
        help='Clé S3 du fichier (ex: 2026/02/20/OPCP_backup_20260220_143000.sql)'
    )
    download_parser.add_argument(
        '--local-dir',
        default='./backups',
        help='Répertoire local de destination'
    )
    
    # Commande restore
    restore_parser = subparsers.add_parser('restore', help='Restaurer depuis S3')
    restore_parser.add_argument(
        's3_key',
        help='Clé S3 du fichier à restaurer'
    )
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_s3_backups(args.bucket, args.prefix, args.provider)
    elif args.command == 'download':
        download_from_s3(args.s3_key, args.bucket, args.local_dir, args.provider)
    elif args.command == 'restore':
        success = restore_from_s3(args.s3_key, args.bucket, args.provider)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
