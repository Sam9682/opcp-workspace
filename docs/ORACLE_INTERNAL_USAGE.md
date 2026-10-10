# Utilisation interne de l'Oracle AI par l'application

## Introduction

L'application OPCP peut utiliser l'Oracle AI en interne pour automatiser certaines tâches d'analyse et de génération de contenu.

## Cas d'usage implémentés

### 1. Analyse automatique du forum

#### Widget sur la page d'accueil

Le widget Oracle sur la page d'accueil permet aux utilisateurs de lancer une analyse complète du forum en un clic.

**Fonctionnalités:**
- Résumé des discussions principales
- Prédiction de perte d'emplois à 5, 10 et 20 ans
- Identification des sujets clés
- Analyse du sentiment général
- Niveau de confiance de l'analyse

**Code:**
```typescript
// frontend/src/components/OracleWidget.tsx
const analyzeForumMessages = async () => {
  const result = await oracleService.analyzeForumMessages('kiro');
  // Afficher les résultats
};
```

**Backend:**
```python
# app/oracle/service.py
@staticmethod
async def analyze_forum(db: Session, ai_provider: str = "kiro"):
    # Récupérer tous les topics et posts
    topics = db.query(Topic).all()
    posts = db.query(Post).all()
    
    # Construire le contexte
    forum_content = []
    for topic in topics:
        forum_content.append(f"Sujet: {topic.title}")
        # Ajouter les posts...
    
    # Interroger l'IA
    question = """
    Analyse tous les messages du forum et réponds:
    1. Résumé des discussions
    2. Pourcentage d'emplois supprimés (5, 10, 20 ans)
    3. Sujets clés
    4. Sentiment général
    5. Niveau de confiance
    """
    
    result = await provider.query(question, context)
    return ForumAnalysisResponse(...)
```

## Cas d'usage futurs

### 2. Génération automatique de rapports

**Objectif:** Générer des rapports mensuels sur l'activité de l'PSMC

**Implémentation:**
```python
# app/oracle/service.py
@staticmethod
async def generate_monthly_report(db: Session, month: int, year: int):
    """Générer un rapport mensuel automatique"""
    
    # Récupérer les données du mois
    events = db.query(Event).filter(
        extract('month', Event.date) == month,
        extract('year', Event.date) == year
    ).all()
    
    forum_activity = db.query(Post).filter(
        extract('month', Post.created_at) == month,
        extract('year', Post.created_at) == year
    ).count()
    
    new_members = db.query(User).filter(
        extract('month', User.created_at) == month,
        extract('year', User.created_at) == year
    ).count()
    
    # Construire le contexte
    context = f"""
    Événements: {len(events)}
    Messages forum: {forum_activity}
    Nouveaux membres: {new_members}
    """
    
    # Interroger l'Oracle
    question = """
    Génère un rapport mensuel professionnel incluant:
    - Résumé de l'activité
    - Points forts du mois
    - Recommandations pour le mois prochain
    - Statistiques clés
    """
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, context)
    
    return result["answer"]
```

**Utilisation:**
```python
# Dans un scheduler (app/scheduler.py)
@scheduler.scheduled_job('cron', day=1, hour=9)
async def monthly_report_job():
    """Générer le rapport mensuel le 1er de chaque mois"""
    db = next(get_db())
    
    today = datetime.now()
    last_month = today.month - 1 if today.month > 1 else 12
    year = today.year if today.month > 1 else today.year - 1
    
    report = await OracleService.generate_monthly_report(db, last_month, year)
    
    # Envoyer par email aux admins
    admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
    for admin in admins:
        send_email(admin.email, "Rapport mensuel", report)
```

### 3. Modération automatique du forum

**Objectif:** Détecter les messages inappropriés ou hors sujet

**Implémentation:**
```python
@staticmethod
async def moderate_post(db: Session, post_id: int):
    """Analyser un post pour modération"""
    
    post = db.query(Post).filter(Post.id == post_id).first()
    
    question = """
    Analyse ce message de forum et détermine:
    1. Est-il approprié ? (oui/non)
    2. Est-il en lien avec l'IA ? (oui/non)
    3. Contient-il du spam ? (oui/non)
    4. Niveau de toxicité (0-10)
    5. Recommandation (approuver/modérer/supprimer)
    
    Réponds au format JSON.
    """
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, post.content)
    
    # Parser la réponse et prendre action
    moderation = json.loads(result["answer"])
    
    if moderation["recommendation"] == "supprimer":
        # Notifier les admins
        pass
    
    return moderation
```

### 4. Suggestions de contenu

**Objectif:** Suggérer des sujets de discussion ou événements

**Implémentation:**
```python
@staticmethod
async def suggest_topics(db: Session):
    """Suggérer des sujets de discussion pertinents"""
    
    # Analyser les topics existants
    topics = db.query(Topic).order_by(Topic.created_at.desc()).limit(50).all()
    
    context = "\n".join([t.title for t in topics])
    
    question = """
    Basé sur les sujets récents du forum, suggère 5 nouveaux sujets
    de discussion pertinents sur l'IA qui pourraient intéresser la communauté.
    
    Format: Liste numérotée avec titre et description courte.
    """
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, context)
    
    return result["answer"]
```

### 5. Réponses automatiques aux questions fréquentes

**Objectif:** Répondre automatiquement aux questions courantes

**Implémentation:**
```python
@staticmethod
async def auto_respond_to_post(db: Session, post_id: int):
    """Générer une réponse automatique si pertinent"""
    
    post = db.query(Post).filter(Post.id == post_id).first()
    topic = db.query(Topic).filter(Topic.id == post.topic_id).first()
    
    # Vérifier si c'est une question
    if not ("?" in post.content):
        return None
    
    context = f"""
    Sujet: {topic.title}
    Question: {post.content}
    """
    
    question = """
    Si cette question est une question fréquente sur l'IA,
    fournis une réponse courte et précise.
    Sinon, réponds "NON_APPLICABLE".
    """
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, context)
    
    if "NON_APPLICABLE" not in result["answer"]:
        # Créer un post de réponse automatique
        auto_post = Post(
            topic_id=topic.id,
            author_id=1,  # Bot user
            content=f"🤖 Réponse automatique:\n\n{result['answer']}"
        )
        db.add(auto_post)
        db.commit()
    
    return result["answer"]
```

### 6. Analyse de sentiment des membres

**Objectif:** Comprendre le moral et l'engagement de la communauté

**Implémentation:**
```python
@staticmethod
async def analyze_member_sentiment(db: Session, user_id: int):
    """Analyser le sentiment d'un membre basé sur ses posts"""
    
    posts = db.query(Post).filter(Post.author_id == user_id).limit(20).all()
    
    context = "\n".join([p.content for p in posts])
    
    question = """
    Analyse le sentiment général de cet utilisateur basé sur ses messages:
    1. Sentiment (positif/neutre/négatif)
    2. Niveau d'engagement (1-10)
    3. Sujets d'intérêt principaux
    4. Recommandations pour améliorer son expérience
    
    Format JSON.
    """
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, context)
    
    return json.loads(result["answer"])
```

### 7. Prédictions d'événements

**Objectif:** Prédire le succès d'un événement avant sa création

**Implémentation:**
```python
@staticmethod
async def predict_event_success(db: Session, event_data: dict):
    """Prédire le succès d'un événement"""
    
    # Analyser les événements passés
    past_events = db.query(Event).all()
    
    context = f"""
    Événements passés: {len(past_events)}
    Nouvel événement:
    - Titre: {event_data['title']}
    - Description: {event_data['description']}
    - Date: {event_data['date']}
    - Capacité: {event_data['max_participants']}
    """
    
    question = """
    Prédis le succès de cet événement:
    1. Taux de participation estimé (%)
    2. Niveau d'intérêt (1-10)
    3. Recommandations pour améliorer l'attractivité
    4. Meilleur moment pour l'organiser
    
    Format JSON.
    """
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, context)
    
    return json.loads(result["answer"])
```

## Intégration dans les tâches planifiées

### Configuration du scheduler

```python
# app/scheduler.py
from app.oracle.service import OracleService

# Rapport mensuel
@scheduler.scheduled_job('cron', day=1, hour=9)
async def monthly_report():
    db = next(get_db())
    report = await OracleService.generate_monthly_report(db, ...)
    # Envoyer aux admins

# Analyse hebdomadaire du forum
@scheduler.scheduled_job('cron', day_of_week='mon', hour=10)
async def weekly_forum_analysis():
    db = next(get_db())
    analysis = await OracleService.analyze_forum(db)
    # Sauvegarder ou envoyer

# Suggestions de contenu
@scheduler.scheduled_job('cron', day_of_week='wed', hour=14)
async def suggest_weekly_topics():
    db = next(get_db())
    suggestions = await OracleService.suggest_topics(db)
    # Notifier les admins
```

## Webhooks et notifications

### Notification des admins

```python
async def notify_admins_with_oracle_insight(db: Session, event_type: str, data: dict):
    """Envoyer une notification enrichie par l'Oracle"""
    
    # Générer un insight avec l'Oracle
    question = f"Analyse cet événement et donne des recommandations: {event_type}"
    
    provider = get_ai_provider("kiro")
    result = await provider.query(question, json.dumps(data))
    
    # Envoyer aux admins
    admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
    for admin in admins:
        notification = Notification(
            user_id=admin.id,
            title=f"Insight Oracle: {event_type}",
            message=result["answer"],
            type=NotificationType.SYSTEM
        )
        db.add(notification)
    
    db.commit()
```

## Bonnes pratiques

### 1. Gestion du cache

Pour éviter de surcharger l'IA avec les mêmes questions:

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Cache simple en mémoire
oracle_cache = {}

async def ask_oracle_with_cache(question: str, ttl: int = 3600):
    """Interroger l'Oracle avec cache"""
    
    cache_key = hash(question)
    
    if cache_key in oracle_cache:
        cached_data, timestamp = oracle_cache[cache_key]
        if datetime.now() - timestamp < timedelta(seconds=ttl):
            return cached_data
    
    # Interroger l'Oracle
    result = await OracleService.ask_oracle(...)
    
    # Mettre en cache
    oracle_cache[cache_key] = (result, datetime.now())
    
    return result
```

### 2. Gestion des erreurs

```python
async def safe_oracle_query(question: str, fallback: str = "Analyse non disponible"):
    """Interroger l'Oracle avec gestion d'erreur"""
    
    try:
        result = await OracleService.ask_oracle(...)
        return result
    except Exception as e:
        logger.error(f"Oracle query failed: {e}")
        return {"answer": fallback}
```

### 3. Monitoring

```python
from app.models.audit import AuditLog

async def log_oracle_usage(user_id: int, question: str, result: dict):
    """Logger l'utilisation de l'Oracle"""
    
    audit = AuditLog(
        user_id=user_id,
        action="oracle_query",
        details={
            "question": question[:100],
            "provider": result["provider"],
            "processing_time": result["processing_time"],
            "tokens_used": result.get("tokens_used")
        }
    )
    db.add(audit)
    db.commit()
```

## Conclusion

L'Oracle AI peut être utilisé en interne par l'application pour:
- Automatiser les analyses
- Générer du contenu
- Modérer les discussions
- Prédire les tendances
- Améliorer l'expérience utilisateur

Toutes ces fonctionnalités peuvent être implémentées en suivant les exemples ci-dessus et en les adaptant aux besoins spécifiques de l'application.
