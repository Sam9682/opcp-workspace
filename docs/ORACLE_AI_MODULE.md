# Module L'Oracle (AI)

## Vue d'ensemble

Le module "L'Oracle (AI)" est une interface d'IA agentique réutilisable qui permet aux utilisateurs d'interroger différents fournisseurs d'IA sur des questions liées à l'intelligence artificielle et son impact sur l'humanité.

## Caractéristiques

### 1. Interface utilisateur conversationnelle
- Chat en temps réel avec l'IA
- Historique des conversations
- Sélection du fournisseur d'IA
- Interface moderne et responsive

### 2. Fournisseurs d'IA supportés

#### Kiro AI (par défaut)
- Utilise kiro-cli en session Ubuntu locale
- Exécution en arrière-plan via subprocess
- Pas de clé API requise

#### Shai AI (OVH)
- Service d'IA d'OVH Cloud
- Nécessite une clé API OVH
- Configuration via variables d'environnement

#### OpenAI
- GPT-4 d'OpenAI
- Nécessite une clé API OpenAI
- Option de secours

### 3. Analyse automatique du forum

Le module peut analyser automatiquement les messages du forum pour:
- Générer un résumé des discussions
- Prédire le pourcentage de perte d'emplois à 5, 10 et 20 ans
- Identifier les sujets clés
- Analyser le sentiment général
- Fournir un niveau de confiance

### 4. Intégration interne

L'application peut utiliser l'Oracle en interne pour:
- Analyser les tendances du forum
- Générer des insights automatiques
- Créer des rapports périodiques
- Répondre aux questions des utilisateurs

## Architecture

### Backend (FastAPI)

```
app/oracle/
├── __init__.py
├── router.py           # Endpoints API
├── service.py          # Logique métier
├── schemas.py          # Modèles Pydantic
└── ai_providers.py     # Implémentations des fournisseurs d'IA

app/models/
└── oracle.py           # Modèle SQLAlchemy
```

### Frontend (React + TypeScript)

```
frontend/src/
├── pages/
│   └── OraclePage.tsx          # Page principale
├── components/
│   └── OracleWidget.tsx        # Widget pour la page d'accueil
└── services/
    └── oracleService.ts        # Service API
```

## Installation

### 1. Backend

#### Installer kiro-cli (Ubuntu)
```bash
# Suivre les instructions d'installation de Kiro
# https://kiro.ai/docs/installation
```

#### Configuration des variables d'environnement
```bash
# Copier .env.example vers .env
cp .env.example .env

# Éditer .env et ajouter vos clés API
SHAI_API_KEY=your_shai_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

#### Exécuter les migrations
```bash
alembic upgrade head
```

### 2. Frontend

Aucune installation supplémentaire requise. Le module est intégré automatiquement.

## Utilisation

### Interface utilisateur

1. Connectez-vous à l'application
2. Accédez au menu "L'Oracle (AI)"
3. Sélectionnez votre fournisseur d'IA préféré
4. Posez vos questions

### Widget sur la page d'accueil

Le widget Oracle apparaît automatiquement sur la page d'accueil pour les utilisateurs connectés. Il permet de:
- Lancer une analyse du forum en un clic
- Voir les prédictions de perte d'emplois
- Identifier les sujets clés

### API Endpoints

#### POST /api/oracle/ask
Poser une question à l'Oracle

```json
{
  "question": "Quel est l'impact de l'IA sur l'emploi ?",
  "context": "Contexte optionnel",
  "ai_provider": "kiro",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

#### GET /api/oracle/history
Récupérer l'historique des questions

#### POST /api/oracle/analyze/forum
Analyser les messages du forum

```json
{
  "analysis_type": "forum_summary",
  "ai_provider": "kiro"
}
```

#### GET /api/oracle/providers
Liste des fournisseurs d'IA disponibles

## Réutilisation dans d'autres applications

Le module Oracle est conçu pour être facilement réutilisable dans d'autres applications opcp-psmc.com.

### Étapes de réutilisation

1. **Copier les fichiers backend**
   ```bash
   cp -r app/oracle/ <votre_app>/oracle/
   cp app/models/oracle.py <votre_app>/models/
   ```

2. **Copier les fichiers frontend**
   ```bash
   cp frontend/src/pages/OraclePage.tsx <votre_frontend>/pages/
   cp frontend/src/components/OracleWidget.tsx <votre_frontend>/components/
   cp frontend/src/services/oracleService.ts <votre_frontend>/services/
   ```

3. **Ajouter les routes**
   - Backend: Inclure le router Oracle dans votre main.py
   - Frontend: Ajouter la route dans App.tsx

4. **Configurer les variables d'environnement**
   - Ajouter les clés API dans .env

5. **Exécuter les migrations**
   ```bash
   alembic upgrade head
   ```

## Rate Limiting

- Questions à l'Oracle: 10 requêtes/minute
- Analyse du forum: 5 requêtes/heure (analyse coûteuse)

## Sécurité

- Authentification requise pour toutes les opérations
- Historique lié à l'utilisateur
- Rate limiting pour éviter les abus
- Validation des entrées avec Pydantic

## Performance

- Exécution asynchrone des requêtes IA
- Timeout de 60 secondes par requête
- Cache possible (à implémenter si nécessaire)

## Évolutions futures

- [ ] Support de plus de fournisseurs d'IA (Claude, Mistral, etc.)
- [ ] Cache des réponses fréquentes
- [ ] Analyse de sentiment en temps réel
- [ ] Génération de rapports PDF
- [ ] Webhooks pour notifications
- [ ] API publique avec authentification par token

## Support

Pour toute question ou problème, contactez l'équipe de développement à contact@opcp-psmc.com

## Licence

Ce module fait partie de l'application OPCP et est soumis aux mêmes conditions de licence.
