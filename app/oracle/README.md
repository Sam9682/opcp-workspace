# Oracle AI Module

Module d'IA agentique pour OPCP et applications opcp-psmc.com

## Structure

- `router.py` - Endpoints FastAPI
- `service.py` - Logique métier et orchestration
- `schemas.py` - Modèles de données Pydantic
- `ai_providers.py` - Implémentations des fournisseurs d'IA

## Fournisseurs d'IA

### Kiro AI (défaut)
- Exécution locale via kiro-cli
- Pas de clé API requise
- Idéal pour le développement

### Shai AI (OVH)
- Service cloud d'OVH
- Nécessite SHAI_API_KEY
- Production recommandée

### OpenAI
- GPT-4
- Nécessite OPENAI_API_KEY
- Option de secours

## Utilisation

```python
from app.oracle.service import OracleService
from app.oracle.schemas import OracleQuery

# Poser une question
query = OracleQuery(
    question="Quel est l'impact de l'IA sur l'emploi ?",
    ai_provider="kiro"
)

response = await OracleService.ask_oracle(db, query, user_id)
```

## Endpoints

- `POST /api/oracle/ask` - Poser une question
- `GET /api/oracle/history` - Historique utilisateur
- `POST /api/oracle/analyze/forum` - Analyser le forum
- `GET /api/oracle/providers` - Liste des fournisseurs

## Configuration

Variables d'environnement requises:

```bash
# Optionnel - Kiro fonctionne sans configuration
SHAI_API_KEY=your_key
OPENAI_API_KEY=your_key
```

## Tests

```bash
# Tester l'endpoint
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Test question",
    "ai_provider": "kiro"
  }'
```
