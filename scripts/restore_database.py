#!/usr/bin/env python3
"""
Script de restauration de la base de données PostgreSQL OPCP
"""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


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


def restore_backup(backup_file: str) -> bool:
    """
    Restaure une sauvegarde de la base de données PostgreSQL
    
    Args:
        backup_file: Chemin vers le fichier de sauvegarde
        
    Returns:
        True si la restauration a réussi, False sinon
    """
    # Vérifier que le fichier existe
    backup_path = Path(backup_file)
    if not backup_path.exists():
        print(f"❌ Erreur: Le fichier {backup_file} n'existe pas")
        return False
    
    # Charger l'URL de la base de données
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ Erreur: DATABASE_URL n'est pas défini dans les variables d'environnement")
        return False
    
    # Parser l'URL
    db_config = parse_database_url(database_url)
    
    print(f"⚠️  ATTENTION: Cette opération va écraser la base de données '{db_config['database']}'")
    response = input("Êtes-vous sûr de vouloir continuer? (oui/non): ")
    
    if response.lower() not in ['oui', 'yes', 'y', 'o']:
        print("❌ Restauration annulée")
        return False
    
    print(f"\n🔄 Restauration de la base de données depuis {backup_file}...")
    
    # Préparer l'environnement
    env = os.environ.copy()
    env['PGPASSWORD'] = db_config['password']
    
    # Commande pg_restore
    cmd = [
        'pg_restore',
        '-h', db_config['host'],
        '-p', str(db_config['port']),
        '-U', db_config['username'],
        '-d', db_config['database'],
        '--clean',  # Nettoyer la base avant restauration
        '--if-exists',  # Ne pas échouer si les objets n'existent pas
        str(backup_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        
        # pg_restore peut retourner des warnings même en cas de succès
        if result.returncode == 0 or "errors ignored" in result.stderr.lower():
            print("✅ Restauration réussie!")
            if result.stderr:
                print("\n⚠️  Avertissements:")
                print(result.stderr)
            return True
        else:
            print(f"❌ Erreur lors de la restauration")
            print(f"Code de retour: {result.returncode}")
            print(f"Sortie d'erreur: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Restauration de la base de données OPCP")
    parser.add_argument(
        'backup_file',
        help='Chemin vers le fichier de sauvegarde à restaurer'
    )
    
    args = parser.parse_args()
    
    success = restore_backup(args.backup_file)
    sys.exit(0 if success else 1)
