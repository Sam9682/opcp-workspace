# Oracle AI - Démarrage Rapide

## Installation en 5 minutes

### 1. Vérifier l'installation

```bash
python3 test_oracle_module.py
```

Tous les fichiers doivent être présents (✅).

### 2. Configurer les variables d'environnement

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer .env et ajouter vos clés API (optionnel)
nano .env
```

Ajouter:
```bash
# Pour Shai AI (OVH)
SHAI_API_KEY=your_key_here

# Pour OpenAI (optionnel)
OPENAI_API_KEY=your_key_here
```

### 3. Exécuter les migrations

```bash
# Créer la table oracle_queries
alembic upgrade head
```

### 4. Installer kiro-cli (optionnel)

```bash
# Pour utiliser le fournisseur Kiro AI local
bash scripts/install_kiro_cli.sh
```

### 5. Démarrer l'application

```bash
# Backend
uvicorn app.main:app --reload

# Frontend (dans un autre terminal)
cd frontend
npm run dev
```

### 6. Tester

1. Ouvrir http://localhost:5173
2. Se connecter
3. Cliquer sur "🔮 L'Oracle (AI)" dans le menu
4. Poser une question

## Utilisation

### Interface utilisateur

1. **Sélectionner le fournisseur d'IA**
   - Shai AI (OVH Cloud, par défaut)
   - Kiro AI (local)
   - OpenAI (GPT-4)

2. **Poser une question**
   - Taper votre question
   - Cliquer sur 🚀

3. **Voir l'historique**
   - Cliquer sur "📜 Historique"
   - Recharger une conversation précédente

### Widget sur la page d'accueil

Le widget Oracle apparaît automatiquement sur la page d'accueil pour les utilisateurs connectés.

**Analyser le forum:**
1. Cliquer sur "🚀 Analyser le forum"
2. Attendre l'analyse (peut prendre 30-60 secondes)
3. Voir les résultats:
   - Résumé des discussions
   - Prédictions de perte d'emplois (5, 10, 20 ans)
   - Sujets clés
   - Sentiment général

### API

#### Poser une question

```bash
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "Quel est l'impact de l'IA sur l'emploi ?",
    "ai_provider": "kiro",
    "temperature": 0.7,
    "max_tokens": 2000
  }'
```

#### Analyser le forum

```bash
curl -X POST http://localhost:8000/api/oracle/analyze/forum \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "analysis_type": "forum_summary",
    "ai_provider": "kiro"
  }'
```

## Dépannage

### Erreur: "kiro-cli not found"

**Solution 1:** Installer kiro-cli
```bash
bash scripts/install_kiro_cli.sh
```

**Solution 2:** Utiliser un autre fournisseur
```typescript
// Dans l'interface, sélectionner "Shai AI" ou "OpenAI"
```

### Erreur: "SHAI_API_KEY not configured"

```bash
# Ajouter la clé dans .env
echo "SHAI_API_KEY=your_key" >> .env

# Redémarrer l'application
```

### Timeout sur les requêtes

Les requêtes peuvent prendre jusqu'à 60 secondes. Si le timeout est trop court:

1. Augmenter le timeout dans `app/oracle/ai_providers.py`
2. Utiliser un fournisseur plus rapide (Kiro local)

### Rate limit dépassé

- Questions: 10/minute
- Analyse forum: 5/heure

Attendre quelques minutes avant de réessayer.

## Exemples de questions

### Questions générales sur l'IA

- "Quel est l'impact de l'IA sur l'emploi ?"
- "Comment l'IA peut-elle aider l'humanité ?"
- "Quels sont les risques de l'IA ?"
- "Quelle est la différence entre IA faible et IA forte ?"

### Questions techniques

- "Explique-moi le machine learning"
- "Comment fonctionne un réseau de neurones ?"
- "Qu'est-ce que le deep learning ?"
- "Quelle est la différence entre supervised et unsupervised learning ?"

### Questions philosophiques

- "L'IA peut-elle avoir une conscience ?"
- "Quel est le rôle de l'humain dans un monde avec l'IA ?"
- "Comment garantir une IA éthique ?"

## Prochaines étapes

1. **Personnaliser les analyses**
   - Modifier `app/oracle/service.py`
   - Ajouter vos propres méthodes d'analyse

2. **Intégrer dans d'autres pages**
   - Utiliser `OracleWidget` n'importe où
   - Créer des analyses spécifiques

3. **Automatiser les analyses**
   - Créer des tâches planifiées
   - Envoyer des rapports par email

4. **Réutiliser dans d'autres applications**
   - Suivre le guide d'intégration
   - Adapter à vos besoins

## Support

- Documentation complète: `docs/ORACLE_AI_MODULE.md`
- Guide d'intégration: `docs/ORACLE_INTEGRATION_GUIDE.md`
- Contact: contact@opcp-psmc.com
