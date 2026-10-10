# Oracle AI - Solution pour l'erreur "kiro-cli: not found"

## Problème
L'Oracle AI était configuré pour utiliser "kiro" comme fournisseur d'IA par défaut, mais `kiro-cli` n'était pas installé dans le container Docker, causant l'erreur:
```
2026-02-19 10:42:49 - OPCP - ERROR - Kiro CLI error: /bin/sh: 1: kiro-cli: not found
```

## Solution appliquée
Installation automatique de Kiro CLI dans le container Docker au moment du build.

### Fichiers modifiés

1. **Dockerfile**
   - Ajout de l'installation de Kiro CLI via `curl -fsSL https://cli.kiro.dev/install | bash`
   - Configuration de la variable d'environnement PATH pour inclure `/root/.local/bin`
   - Kiro CLI est maintenant disponible automatiquement dans le container

2. **app/oracle/ai_providers.py**
   - Amélioration de la gestion du PATH pour trouver kiro-cli
   - Ajout de plusieurs chemins possibles: `/root/.local/bin`, `/home/ubuntu/.local/bin`, `~/.local/bin`
   - Message d'erreur amélioré suggérant de reconstruire le container

3. **Configuration par défaut restaurée**
   - `app/oracle/schemas.py`: default = "kiro"
   - `app/oracle/router.py`: Kiro AI marqué comme default
   - `oracle_config.json`: Kiro en premier avec `"default": true`
   - `frontend/src/services/oracleService.ts`: default = "kiro"
   - `frontend/src/pages/OraclePage.tsx`: provider initial = "kiro"

4. **Documentation mise à jour**
   - `.env.example`: Kiro AI comme default, aucune configuration requise
   - `.env`: Commentaires mis à jour

## Avantages de cette solution

✅ **Gratuit**: Kiro AI est inclus, pas besoin de clé API
✅ **Automatique**: Installation au build du container
✅ **Pas de configuration**: Fonctionne out-of-the-box
✅ **Fallback disponible**: OpenAI et Shai AI restent disponibles comme alternatives

## Déploiement

Pour appliquer cette solution, reconstruisez le container Docker:

```bash
# Arrêter les containers
docker-compose down

# Reconstruire avec la nouvelle image
docker-compose build --no-cache

# Redémarrer
docker-compose up -d
```

## Test

Après le redémarrage, testez l'Oracle:

```bash
# Vérifier que kiro-cli est installé dans le container
docker-compose exec web kiro-cli --version

# Tester l'Oracle via l'API
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Bonjour Oracle, comment vas-tu?"}'
```

## Alternatives (optionnelles)

Si vous préférez utiliser un autre fournisseur d'IA, ajoutez les clés API dans `.env`:

### OpenAI
```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
```

### Shai AI (OVH)
```bash
SHAI_API_KEY=your_shai_api_key_here
SHAI_API_URL=https://api.ovh.com/shai/v1/chat
```

## Notes techniques

- Kiro CLI s'installe dans `/root/.local/bin` dans le container
- La variable PATH est configurée pour inclure ce répertoire
- Le code Python vérifie plusieurs emplacements possibles
- Timeout de 60 secondes pour les requêtes Kiro CLI
- Les utilisateurs peuvent changer de fournisseur dans l'interface web
