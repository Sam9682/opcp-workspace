# Guide de déploiement - Fix Oracle AI avec Kiro CLI

## Résumé
Kiro CLI est maintenant installé automatiquement dans le container Docker, permettant à l'Oracle AI de fonctionner sans configuration supplémentaire.

## Étapes de déploiement

### 1. Arrêter l'application
```bash
docker-compose down
```

### 2. Reconstruire les containers
```bash
# Rebuild sans cache pour forcer l'installation de Kiro CLI
docker-compose build --no-cache web
```

### 3. Démarrer l'application
```bash
docker-compose up -d
```

### 4. Vérifier l'installation de Kiro CLI
```bash
# Vérifier que kiro-cli est installé
docker-compose exec web kiro-cli --version

# Devrait afficher la version de Kiro CLI
```

### 5. Tester l'Oracle AI
```bash
# Test via curl (sans authentification)
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Bonjour Oracle, peux-tu me dire ce qu'\''est l'\''intelligence artificielle?",
    "ai_provider": "kiro"
  }'
```

### 6. Vérifier les logs
```bash
# Voir les logs de l'application
docker-compose logs -f web

# Rechercher les erreurs Kiro CLI
docker-compose logs web | grep -i "kiro"
```

## Vérification dans l'interface web

1. Connectez-vous à l'application: http://localhost:3000
2. Allez dans "L'Oracle (AI)" 🔮
3. Vérifiez que "Kiro AI (Local - Gratuit)" est sélectionné par défaut
4. Posez une question test
5. Vérifiez que la réponse arrive sans erreur

## Troubleshooting

### Erreur: "kiro-cli: not found" persiste
```bash
# Vérifier que le Dockerfile a bien été modifié
cat Dockerfile | grep -A 5 "Kiro CLI"

# Forcer un rebuild complet
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Erreur: "Permission denied"
```bash
# Vérifier les permissions dans le container
docker-compose exec web ls -la /root/.local/bin/

# Vérifier la variable PATH
docker-compose exec web echo $PATH
```

### Kiro CLI timeout
```bash
# Augmenter le timeout dans ai_providers.py si nécessaire
# Actuellement configuré à 60 secondes
```

### Utiliser un fournisseur alternatif
Si Kiro CLI ne fonctionne pas, vous pouvez utiliser OpenAI ou Shai:

```bash
# Ajouter dans .env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4

# Redémarrer
docker-compose restart web
```

Puis sélectionner "OpenAI GPT-4" dans l'interface web.

## Rollback

Si vous devez revenir en arrière:

```bash
# Revenir au commit précédent
git checkout HEAD~1

# Reconstruire
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Notes importantes

- ✅ Kiro CLI est gratuit et ne nécessite pas de clé API
- ✅ L'installation se fait automatiquement au build du container
- ✅ Aucune configuration manuelle requise
- ⚠️ Le premier build peut prendre quelques minutes supplémentaires
- ⚠️ Assurez-vous d'avoir une connexion internet pour télécharger Kiro CLI

## Support

En cas de problème:
1. Vérifier les logs: `docker-compose logs web`
2. Vérifier l'installation: `docker-compose exec web kiro-cli --version`
3. Consulter ORACLE_FIX_SUMMARY.md pour plus de détails
