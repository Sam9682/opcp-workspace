# Intégration de Kiro CLI dans l'application OPCP

## Vue d'ensemble

L'application OPCP utilise le module "Oracle AI" qui permet aux utilisateurs de poser des questions à une IA agentique. Kiro CLI est maintenant intégré comme fournisseur d'IA par défaut, offrant une solution gratuite et sans configuration.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                          │
│  - OraclePage.tsx: Interface utilisateur                    │
│  - oracleService.ts: Appels API                             │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP POST /api/oracle/ask
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                Backend (FastAPI) - Container Docker          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ app/oracle/router.py                                 │   │
│  │  - Endpoint /api/oracle/ask                         │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                        │
│  ┌─────────────────▼──────────────────────────────────┐   │
│  │ app/oracle/service.py                               │   │
│  │  - OracleService.ask_oracle()                       │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                        │
│  ┌─────────────────▼──────────────────────────────────┐   │
│  │ app/oracle/ai_providers.py                          │   │
│  │  - KiroAIProvider.query()                           │   │
│  │  - ShaiAIProvider.query()                           │   │
│  │  - OpenAIProvider.query()                           │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                        │
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────┐      │
│  │ Kiro CLI (/root/.local/bin/kiro-cli)             │      │
│  │  - Installé au build du container                 │      │
│  │  - Exécuté via subprocess                         │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Installation de Kiro CLI

### Dans le Dockerfile

```dockerfile
# Install Amazon Kiro CLI for Oracle AI
RUN curl -fsSL https://cli.kiro.dev/install | bash && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Ensure Kiro CLI is in PATH for all users
ENV PATH="/root/.local/bin:${PATH}"
```

### Emplacement dans le container
- Binaire: `/root/.local/bin/kiro-cli`
- Configuration: `/root/.kiro/`
- PATH: Configuré via ENV dans le Dockerfile

## Utilisation dans le code

### Backend - KiroAIProvider

```python
# app/oracle/ai_providers.py
class KiroAIProvider(AIProvider):
    async def query(self, question: str, context: Optional[str] = None, 
                   temperature: float = 0.7, max_tokens: int = 2000):
        # Construction du prompt
        prompt = f"Contexte: {context}\n\nQuestion: {question}" if context else question
        
        # Configuration de l'environnement
        env = os.environ.copy()
        env['PATH'] = '/root/.local/bin:/home/ubuntu/.local/bin:' + env.get('PATH', '')
        
        # Exécution de kiro-cli
        process = await asyncio.create_subprocess_shell(
            f'kiro-cli chat --no-interactive "{prompt}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Timeout de 60 secondes
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
        
        return {
            "answer": stdout.decode().strip(),
            "processing_time": time.time() - start_time,
            "tokens_used": len(answer.split()),
            "provider": "kiro"
        }
```

### Frontend - Sélection du provider

```typescript
// frontend/src/pages/OraclePage.tsx
const [provider, setProvider] = useState<'kiro' | 'shai' | 'openai'>('kiro');

// Envoi de la requête
const response = await oracleService.askOracle({
  question: input,
  ai_provider: provider,
  temperature: 0.7,
  max_tokens: 2000
});
```

## Configuration

### Aucune configuration requise pour Kiro AI
Kiro AI fonctionne out-of-the-box sans clé API ni configuration.

### Fournisseurs alternatifs (optionnels)

#### OpenAI
```bash
# .env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
```

#### Shai AI (OVH)
```bash
# .env
SHAI_API_KEY=your_key
SHAI_API_URL=https://api.ovh.com/shai/v1/chat
```

## Déploiement

### Build du container
```bash
docker-compose build --no-cache web
```

### Démarrage
```bash
docker-compose up -d
```

### Vérification
```bash
# Vérifier l'installation
docker-compose exec web kiro-cli --version

# Tester l'API
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Test", "ai_provider": "kiro"}'
```

## Tests

### Script de test automatique
```bash
./test_kiro_installation.sh
```

Ce script vérifie:
1. ✅ Container en cours d'exécution
2. ✅ kiro-cli installé
3. ✅ PATH configuré
4. ✅ API Oracle fonctionnelle
5. ✅ Absence d'erreurs dans les logs

### Test manuel dans l'interface
1. Ouvrir http://localhost:3000
2. Se connecter
3. Aller dans "L'Oracle (AI)" 🔮
4. Vérifier que "Kiro AI (Local - Gratuit)" est sélectionné
5. Poser une question
6. Vérifier la réponse

## Gestion des erreurs

### Erreur: "kiro-cli: not found"
**Cause**: Kiro CLI n'est pas installé ou PATH incorrect

**Solution**:
```bash
# Reconstruire le container
docker-compose build --no-cache web
docker-compose up -d
```

### Erreur: "Timeout"
**Cause**: La requête prend plus de 60 secondes

**Solution**: Augmenter le timeout dans `ai_providers.py` ou utiliser un autre provider

### Erreur: "Permission denied"
**Cause**: Problème de permissions sur le binaire

**Solution**:
```bash
docker-compose exec web chmod +x /root/.local/bin/kiro-cli
```

## Avantages de cette solution

| Aspect | Avantage |
|--------|----------|
| 💰 Coût | Gratuit, pas de clé API requise |
| ⚙️ Configuration | Aucune configuration nécessaire |
| 🚀 Déploiement | Installation automatique au build |
| 🔒 Sécurité | Exécution locale dans le container |
| 🔄 Fallback | OpenAI et Shai disponibles en alternative |
| 📦 Portabilité | Fonctionne dans n'importe quel environnement Docker |

## Limitations

- ⏱️ Timeout de 60 secondes par requête
- 🌐 Nécessite une connexion internet au build (pour télécharger Kiro CLI)
- 💾 Augmente légèrement la taille de l'image Docker
- 🔧 Pas de support pour temperature/max_tokens (paramètres ignorés)

## Monitoring

### Logs
```bash
# Voir tous les logs
docker-compose logs -f web

# Filtrer les logs Kiro
docker-compose logs web | grep -i kiro

# Voir les erreurs
docker-compose logs web | grep -i error
```

### Métriques
Les métriques suivantes sont enregistrées dans la base de données:
- `processing_time`: Temps de traitement en secondes
- `tokens_used`: Nombre approximatif de tokens (basé sur le nombre de mots)
- `ai_provider`: Provider utilisé ("kiro", "shai", ou "openai")

## Maintenance

### Mise à jour de Kiro CLI
Pour mettre à jour Kiro CLI vers la dernière version:
```bash
docker-compose build --no-cache web
docker-compose up -d
```

### Désactivation de Kiro AI
Pour désactiver Kiro AI et utiliser uniquement OpenAI/Shai:
1. Configurer les clés API dans `.env`
2. Changer le default dans `app/oracle/schemas.py`
3. Redémarrer: `docker-compose restart web`

## Support

- 📖 Documentation: `docs/ORACLE_*.md`
- 🔧 Configuration: `oracle_config.json`
- 🐛 Troubleshooting: `ORACLE_FIX_SUMMARY.md`
- 🚀 Déploiement: `DEPLOY_ORACLE_FIX.md`
- ✅ Tests: `test_kiro_installation.sh`
