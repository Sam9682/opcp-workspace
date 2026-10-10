# Guide d'intégration du module Oracle AI dans opcp-psmc.com

## Introduction

Ce guide explique comment intégrer le module "L'Oracle (AI)" dans n'importe quelle application de l'écosystème opcp-psmc.com.

## Prérequis

- Application FastAPI (backend)
- Application React + TypeScript (frontend)
- PostgreSQL (base de données)
- Alembic (migrations)

## Étape 1: Backend - Copier les fichiers

### 1.1 Copier le module Oracle

```bash
# Depuis le projet OPCP
cp -r app/oracle/ <votre_projet>/app/oracle/
cp app/models/oracle.py <votre_projet>/app/models/
```

### 1.2 Mettre à jour les imports

Dans `<votre_projet>/app/models/__init__.py`:

```python
from app.models.oracle import OracleQuery
```

Dans `<votre_projet>/app/main.py`:

```python
from app.oracle.router import router as oracle_router

# Dans la fonction de création de l'app
app.include_router(oracle_router)
```

## Étape 2: Base de données

### 2.1 Créer la migration

```bash
cd <votre_projet>

# Créer une nouvelle migration
alembic revision --autogenerate -m "add oracle queries table"
```

### 2.2 Exécuter la migration

```bash
alembic upgrade head
```

## Étape 3: Configuration

### 3.1 Variables d'environnement

Ajouter dans `.env`:

```bash
# Oracle AI Configuration
SHAI_API_KEY=your_shai_api_key_here
SHAI_API_URL=https://api.ovh.com/shai/v1/chat
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
```

### 3.2 Installer kiro-cli (optionnel)

```bash
# Pour utiliser le fournisseur Kiro AI local
bash scripts/install_kiro_cli.sh
```

## Étape 4: Frontend - Copier les fichiers

### 4.1 Copier les composants

```bash
# Depuis le projet OPCP
cp frontend/src/pages/OraclePage.tsx <votre_frontend>/src/pages/
cp frontend/src/components/OracleWidget.tsx <votre_frontend>/src/components/
cp frontend/src/services/oracleService.ts <votre_frontend>/src/services/
```

### 4.2 Ajouter les routes

Dans `<votre_frontend>/src/App.tsx`:

```typescript
import { OraclePage } from './pages/OraclePage';

// Dans les routes
<Route
  path="/oracle"
  element={
    <ProtectedRoute>
      <OraclePage />
    </ProtectedRoute>
  }
/>
```

### 4.3 Ajouter le menu

Dans votre composant de navigation:

```typescript
<Link to="/oracle" className="nav-link">
  <span className="mr-1">🔮</span> L'Oracle (AI)
</Link>
```

## Étape 5: Personnalisation

### 5.1 Adapter le contexte

Dans `app/oracle/service.py`, méthode `analyze_forum()`:

```python
# Adapter selon votre modèle de données
topics = db.query(YourTopicModel).all()
posts = db.query(YourPostModel).all()
```

### 5.2 Personnaliser les questions

Créer des méthodes d'analyse spécifiques à votre application:

```python
@staticmethod
async def analyze_custom_data(
    db: Session,
    data_type: str,
    ai_provider: str = "kiro"
) -> dict:
    """Analyser des données spécifiques à votre application"""
    # Votre logique ici
    pass
```

### 5.3 Adapter l'interface

Modifier `OracleWidget.tsx` pour afficher des analyses spécifiques:

```typescript
const analyzeCustomData = async () => {
  const result = await oracleService.analyzeCustomData('your_data_type');
  // Traiter le résultat
};
```

## Étape 6: Tests

### 6.1 Tester l'API

```bash
# Tester l'endpoint ask
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Test question",
    "ai_provider": "kiro"
  }'
```

### 6.2 Tester l'interface

1. Démarrer l'application
2. Se connecter
3. Accéder à `/oracle`
4. Poser une question
5. Vérifier la réponse

## Étape 7: Déploiement

### 7.1 Variables d'environnement de production

```bash
# Production
SHAI_API_KEY=prod_key_here
OPENAI_API_KEY=prod_key_here
```

### 7.2 Rate limiting

Ajuster les limites dans `app/oracle/router.py`:

```python
@limiter.limit("10/minute")  # Ajuster selon vos besoins
async def ask_oracle(...):
    pass
```

## Cas d'usage spécifiques

### Analyse automatique périodique

Créer une tâche planifiée:

```python
from app.oracle.service import OracleService

async def daily_analysis():
    """Analyse quotidienne automatique"""
    db = next(get_db())
    analysis = await OracleService.analyze_forum(db)
    # Envoyer par email, sauvegarder, etc.
```

### Intégration dans d'autres pages

Utiliser le widget Oracle n'importe où:

```typescript
import { OracleWidget } from '../components/OracleWidget';

// Dans votre composant
<OracleWidget onAnalysisComplete={(analysis) => {
  console.log('Analyse terminée:', analysis);
}} />
```

### API publique

Créer un endpoint public avec authentification par token:

```python
@router.post("/api/public/oracle/ask")
async def public_ask_oracle(
    query: OracleQuery,
    api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    # Vérifier l'API key
    # Exécuter la requête
    pass
```

## Support et maintenance

### Mises à jour

Pour mettre à jour le module Oracle dans votre application:

1. Sauvegarder vos personnalisations
2. Copier les nouveaux fichiers depuis OPCP
3. Réappliquer vos personnalisations
4. Tester

### Dépannage

#### Erreur: "kiro-cli not found"

```bash
# Installer kiro-cli
bash scripts/install_kiro_cli.sh

# Ou utiliser un autre fournisseur
# Dans la requête, spécifier: "ai_provider": "shai"
```

#### Erreur: "SHAI_API_KEY not configured"

```bash
# Ajouter la clé dans .env
echo "SHAI_API_KEY=your_key" >> .env

# Redémarrer l'application
```

#### Timeout sur les requêtes

Augmenter le timeout dans `app/oracle/ai_providers.py`:

```python
timeout=120.0  # Au lieu de 60.0
```

## Exemples d'applications

### Application de gestion de projet

```python
async def analyze_project_risks(db: Session, project_id: int):
    """Analyser les risques d'un projet avec l'Oracle"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    query = OracleQuery(
        question=f"Analyse les risques du projet: {project.description}",
        context=f"Budget: {project.budget}, Deadline: {project.deadline}",
        ai_provider="kiro"
    )
    
    return await OracleService.ask_oracle(db, query)
```

### Application e-commerce

```python
async def analyze_customer_sentiment(db: Session):
    """Analyser le sentiment des avis clients"""
    reviews = db.query(Review).all()
    
    context = "\n".join([r.content for r in reviews[:100]])
    
    query = OracleQuery(
        question="Analyse le sentiment général des avis clients et donne des recommandations",
        context=context,
        ai_provider="shai"
    )
    
    return await OracleService.ask_oracle(db, query)
```

## Conclusion

Le module Oracle AI est maintenant intégré dans votre application opcp-psmc.com. Vous pouvez le personnaliser selon vos besoins spécifiques.

Pour toute question, contactez l'équipe de développement à contact@opcp-psmc.com
