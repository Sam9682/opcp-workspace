#!/usr/bin/env python3
"""
Script de test pour vérifier la configuration des sauvegardes
"""
import os
import sys
import subprocess
from pathlib import Path


def check_command(command: str, name: str) -> bool:
    """Vérifie si une commande est disponible"""
    try:
        result = subprocess.run(
            ['which', command],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ {name} installé: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {name} non trouvé")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de {name}: {e}")
        return False


def check_python_package(package: str) -> bool:
    """Vérifie si un package Python est installé"""
    try:
        __import__(package)
        print(f"✅ Package Python '{package}' installé")
        return True
    except ImportError:
        print(f"❌ Package Python '{package}' non installé")
        return False


def check_env_variable(var: str) -> bool:
    """Vérifie si une variable d'environnement est définie"""
    value = os.getenv(var)
    if value:
        # Masquer les mots de passe
        if 'PASSWORD' in var or 'SECRET' in var or 'KEY' in var:
            display_value = '***'
        else:
            display_value = value[:50] + '...' if len(value) > 50 else value
        print(f"✅ Variable {var} définie: {display_value}")
        return True
    else:
        print(f"❌ Variable {var} non définie")
        return False


def check_aws_credentials() -> bool:
    """Vérifie les credentials AWS"""
    try:
        result = subprocess.run(
            ['aws', 'sts', 'get-caller-identity'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ AWS credentials configurés")
            return True
        else:
            print(f"❌ AWS credentials non configurés")
            print(f"   Exécutez: aws configure")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de la vérification AWS: {e}")
        return False


def check_s3_bucket(bucket: str = "ai-OPCP") -> bool:
    """Vérifie si le bucket S3 existe et est accessible"""
    try:
        result = subprocess.run(
            ['aws', 's3', 'ls', f's3://{bucket}/'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Bucket S3 '{bucket}' accessible")
            return True
        else:
            print(f"❌ Bucket S3 '{bucket}' non accessible")
            print(f"   Créez-le avec: bash scripts/setup_s3_bucket.sh")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de la vérification du bucket: {e}")
        return False


def check_database_connection() -> bool:
    """Vérifie la connexion à la base de données"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL non défini")
        return False
    
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    
    try:
        result = subprocess.run(
            [
                'pg_isready',
                '-h', parsed.hostname,
                '-p', str(parsed.port or 5432),
                '-U', parsed.username,
                '-d', parsed.path.lstrip('/')
            ],
            capture_output=True,
            text=True,
            env={**os.environ, 'PGPASSWORD': parsed.password}
        )
        if result.returncode == 0:
            print(f"✅ Base de données accessible")
            return True
        else:
            print(f"❌ Base de données non accessible")
            print(f"   {result.stdout}")
            return False
    except Exception as e:
        print(f"⚠️  Impossible de vérifier la connexion DB: {e}")
        return False


def main():
    """Exécute tous les tests"""
    print("🔍 Vérification de la configuration des sauvegardes OPCP")
    print("=" * 70)
    
    results = []
    
    # Vérifier les commandes système
    print("\n📦 Commandes système:")
    results.append(check_command('pg_dump', 'pg_dump'))
    results.append(check_command('pg_restore', 'pg_restore'))
    results.append(check_command('aws', 'AWS CLI'))
    
    # Vérifier les packages Python
    print("\n🐍 Packages Python:")
    results.append(check_python_package('boto3'))
    results.append(check_python_package('psycopg2'))
    
    # Vérifier les variables d'environnement
    print("\n🔐 Variables d'environnement:")
    results.append(check_env_variable('DATABASE_URL'))
    
    # Vérifier AWS
    print("\n☁️  Configuration AWS:")
    aws_ok = check_aws_credentials()
    results.append(aws_ok)
    
    if aws_ok:
        results.append(check_s3_bucket())
    
    # Vérifier la connexion DB
    print("\n🗄️  Base de données:")
    results.append(check_database_connection())
    
    # Résumé
    print("\n" + "=" * 70)
    success_count = sum(results)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"✅ Tous les tests réussis ({success_count}/{total_count})")
        print("\n🎉 Vous pouvez maintenant utiliser:")
        print("   python scripts/backup_database.py")
        return 0
    else:
        print(f"⚠️  {success_count}/{total_count} tests réussis")
        print("\n📖 Consultez le guide: scripts/QUICK_START_BACKUP.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
