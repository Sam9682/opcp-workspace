#!/usr/bin/env python3
"""
Script de test pour le module Oracle AI
Vérifie que tous les composants sont correctement installés
"""

import sys
import os
from pathlib import Path

def check_file_exists(filepath: str) -> bool:
    """Vérifier si un fichier existe"""
    exists = Path(filepath).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {filepath}")
    return exists

def main():
    print("🔮 Test du module Oracle AI")
    print("=" * 50)
    
    all_ok = True
    
    # Backend files
    print("\n📦 Fichiers Backend:")
    backend_files = [
        "app/oracle/__init__.py",
        "app/oracle/router.py",
        "app/oracle/service.py",
        "app/oracle/schemas.py",
        "app/oracle/ai_providers.py",
        "app/oracle/README.md",
        "app/models/oracle.py",
    ]
    
    for file in backend_files:
        if not check_file_exists(file):
            all_ok = False
    
    # Frontend files
    print("\n🎨 Fichiers Frontend:")
    frontend_files = [
        "frontend/src/pages/OraclePage.tsx",
        "frontend/src/components/OracleWidget.tsx",
        "frontend/src/services/oracleService.ts",
    ]
    
    for file in frontend_files:
        if not check_file_exists(file):
            all_ok = False
    
    # Documentation
    print("\n📚 Documentation:")
    doc_files = [
        "docs/ORACLE_AI_MODULE.md",
        "docs/ORACLE_INTEGRATION_GUIDE.md",
    ]
    
    for file in doc_files:
        if not check_file_exists(file):
            all_ok = False
    
    # Scripts
    print("\n🔧 Scripts:")
    script_files = [
        "scripts/install_kiro_cli.sh",
    ]
    
    for file in script_files:
        if not check_file_exists(file):
            all_ok = False
    
    # Vérifier les imports Python
    print("\n🐍 Imports Python:")
    try:
        sys.path.insert(0, os.getcwd())
        from app.oracle import router, service, schemas, ai_providers
        print("✅ Tous les imports Python fonctionnent")
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        all_ok = False
    
    # Résumé
    print("\n" + "=" * 50)
    if all_ok:
        print("✅ Tous les tests sont passés!")
        print("\n📝 Prochaines étapes:")
        print("1. Configurer les variables d'environnement dans .env")
        print("2. Exécuter les migrations: alembic upgrade head")
        print("3. Installer kiro-cli: bash scripts/install_kiro_cli.sh")
        print("4. Démarrer l'application et tester /oracle")
        return 0
    else:
        print("❌ Certains tests ont échoué")
        print("Vérifiez que tous les fichiers ont été créés correctement")
        return 1

if __name__ == "__main__":
    sys.exit(main())
