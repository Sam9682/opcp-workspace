# 🔮 Module L'Oracle (AI)

> Interface d'IA agentique réutilisable pour les applications opcp-psmc.com

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/OPCP/oracle-ai)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18+-blue.svg)](https://reactjs.org/)

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Fonctionnalités](#fonctionnalités)
- [Installation rapide](#installation-rapide)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Utilisation](#utilisation)
- [Réutilisation](#réutilisation)
- [Support](#support)

## 🎯 Vue d'ensemble

Le module "L'Oracle (AI)" est une interface conversationnelle d'IA agentique qui permet:

- 💬 **Chat interactif** avec différents fournisseurs d'IA
- 📊 **Analyse automatique** du forum et prédictions
- 🔄 **Réutilisable** dans toutes les applications opcp-psmc.com
- 🚀 **Facile à intégrer** avec documentation complète
- 🔒 **Sécurisé** avec authentification et rate limiting

## ✨ Fonctionnalités

### Interface utilisateur

- ✅ Chat en temps réel avec l'IA
- ✅ Sélection du fournisseur (Kiro, Shai, OpenAI)
- ✅ Historique des conversations
- ✅ Suggestions de questions
- ✅ Interface responsive et moderne

### Widget page d'accueil

- ✅ Analyse automatique du forum
- ✅ Prédictions de perte d'emplois (5, 10, 20 ans)
- ✅ Identification des sujets clés
- ✅ Analyse de sentiment

### API Backend

- ✅ `POST /api/oracle/ask` - Poser une question
- ✅ `GET /api/oracle/history` - Historique
- ✅ `POST /api/oracle/analyze/forum` - Analyser le forum
- ✅ `GET /api/oracle/providers` - Liste des fournisseurs

### Fournisseurs d'IA

| Fournisseur | Type | API Key | Description |
|-------------|------|---------|-------------|
| **Kiro AI** | Local | ❌ Non | IA locale via kiro-cli (défaut) |
| **Shai AI** | Cloud | ✅ Oui | Service d'IA d'OVH Cloud |
| **OpenAI** | Cloud | ✅ Oui | GPT-4 d'OpenAI |

## 🚀 Installation rapide

### 1. Vérifier l'installation

```bash
python3 test_oracle_module.py
```

### 2. Configurer

```bash
cp .env.example .env
# Éditer .env avec vos clés API
```

### 3. Migrer la base de données

```bash
alembic upgrade head
```

### 4. Démarrer

```bash
# Backend
uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev
```

### 5. Tester

Ouvrir http://localhost:5173 et cliquer sur "🔮 L'Oracle (AI)"

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Guide complet](docs/ORACLE_AI_MODULE.md) | Documentation complète du module |
| [Démarrage rapide](docs/ORACLE_QUICK_START.md) | Installation en 5 minutes |
| [Guide d'intégration](docs/ORACLE_INTEGRATION_GUIDE.md) | Intégrer dans vos applications |
| [Utilisation interne](docs/ORACLE_INTERNAL_USAGE.md) | Cas d'usage avancés |
| [Configuration](oracle_config.json) | Fichier de configuration |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ OraclePage   │  │ OracleWidget │  │ oracleService│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │    Router    │  │   Service    │  │   Schemas    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   AI Providers                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Kiro AI    │  │   Shai AI    │  │   OpenAI     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Database (PostgreSQL)                   │
│                    oracle_queries                        │
└─────────────────────────────────────────────────────────┘
```

## 💻 Utilisation

### Interface utilisateur

```typescript
// Poser une question
const response = await oracleService.askOracle({
  question: "Quel est l'impact de l'IA sur l'emploi ?",
  ai_provider: "kiro",
  temperature: 0.7,
  max_tokens: 2000
});
```

### Widget

```typescript
import { OracleWidget } from '../components/OracleWidget';

<OracleWidget onAnalysisComplete={(analysis) => {
  console.log('Analyse:', analysis);
}} />
```

### API

```bash
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Test question",
    "ai_provider": "kiro"
  }'
```

### Programmatique

```python
from app.oracle.service import OracleService
from app.oracle.schemas import OracleQuery

query = OracleQuery(
    question="Quel est l'impact de l'IA ?",
    ai_provider="kiro"
)

response = await OracleService.ask_oracle(db, query, user_id)
```

## 🔄 Réutilisation

### Intégrer dans une nouvelle application

```bash
# 1. Copier les fichiers
cp -r app/oracle/ <votre_app>/oracle/
cp app/models/oracle.py <votre_app>/models/
cp -r frontend/src/pages/OraclePage.tsx <votre_frontend>/pages/
cp -r frontend/src/components/OracleWidget.tsx <votre_frontend>/components/
cp -r frontend/src/services/oracleService.ts <votre_frontend>/services/

# 2. Configurer
cp .env.example .env
# Éditer .env

# 3. Migrer
alembic upgrade head

# 4. Ajouter les routes
# Voir docs/ORACLE_INTEGRATION_GUIDE.md
```

### Personnaliser

```python
# Ajouter un nouveau fournisseur d'IA
class CustomAIProvider(AIProvider):
    async def query(self, question, context, temperature, max_tokens):
        # Votre implémentation
        pass

# Ajouter une nouvelle analyse
@staticmethod
async def analyze_custom_data(db: Session, data_type: str):
    # Votre analyse
    pass
```

## 🔒 Sécurité

- ✅ Authentification JWT requise
- ✅ Rate limiting (10/min questions, 5/h analyses)
- ✅ Validation des entrées avec Pydantic
- ✅ Gestion sécurisée des clés API
- ✅ Timeout sur les requêtes (60s)

## 📊 Métriques

Le module enregistre automatiquement:
- Temps de traitement
- Nombre de tokens utilisés
- Fournisseur d'IA utilisé
- Historique complet

## 🎨 Captures d'écran

### Interface de chat
```
┌─────────────────────────────────────────────────────┐
│  🔮 L'Oracle (AI)                                   │
│  Interface d'IA agentique                           │
├─────────────────────────────────────────────────────┤
│  Fournisseur: [Kiro AI ▼]                          │
│  ┌───────────────────────────────────────────────┐ │
│  │ 🤖 Bienvenue à l'Oracle AI...                 │ │
│  │                                                │ │
│  │ 👤 Quel est l'impact de l'IA sur l'emploi ?  │ │
│  │                                                │ │
│  │ 🤖 L'IA aura un impact significatif...       │ │
│  └───────────────────────────────────────────────┘ │
│  [Votre question...                    ] [🚀]      │
└─────────────────────────────────────────────────────┘
```

### Widget d'analyse
```
┌─────────────────────────────────────────────────────┐
│  🔮 L'Oracle AI              [🚀 Analyser le forum] │
├─────────────────────────────────────────────────────┤
│  📊 Résumé des discussions                          │
│  Les discussions portent principalement sur...      │
│                                                      │
│  📉 Prédictions de perte d'emplois                  │
│  Dans 5 ans:  15.2%                                 │
│  Dans 10 ans: 28.5%                                 │
│  Dans 20 ans: 42.8%                                 │
│                                                      │
│  🏷️ Sujets clés                                     │
│  [IA] [Emploi] [Automatisation] [Éthique]          │
└─────────────────────────────────────────────────────┘
```

## 🛠️ Développement

### Structure des fichiers

```
app/oracle/
├── __init__.py
├── router.py           # Endpoints API
├── service.py          # Logique métier
├── schemas.py          # Modèles Pydantic
├── ai_providers.py     # Implémentations IA
└── README.md

frontend/src/
├── pages/OraclePage.tsx
├── components/OracleWidget.tsx
└── services/oracleService.ts

docs/
├── ORACLE_AI_MODULE.md
├── ORACLE_INTEGRATION_GUIDE.md
├── ORACLE_QUICK_START.md
└── ORACLE_INTERNAL_USAGE.md
```

### Tests

```bash
# Tester le module
python3 test_oracle_module.py

# Tester l'API
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Test", "ai_provider": "kiro"}'
```

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer:

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 Changelog

### Version 1.0.0 (2026-02-18)

- ✅ Interface de chat conversationnel
- ✅ Support de 3 fournisseurs d'IA (Kiro, Shai, OpenAI)
- ✅ Widget d'analyse du forum
- ✅ Prédictions de perte d'emplois
- ✅ Historique des conversations
- ✅ API REST complète
- ✅ Documentation complète
- ✅ Scripts d'installation et de test

## 📞 Support

- **Email:** contact@opcp-psmc.com
- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/OPCP/oracle-ai/issues)

## 📄 Licence

Ce module fait partie de l'application OPCP et est distribué sous licence MIT.

## 🙏 Remerciements

- OPCP - Produit OVH
- opcp-psmc.com - Plateforme de déploiement
- Communauté open source

---

**Développé avec ❤️ par OPCP pour l'écosystème opcp-psmc.com**

🔮 *"L'Oracle voit l'avenir de l'IA et de l'humanité"*
