# OPCP - Guide de Démarrage Rapide

## 🚀 Démarrage avec Docker Compose

### Prérequis
- Docker et Docker Compose installés
- Ports 8000 (backend) et 5173 (frontend) disponibles

### Démarrage

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f app

# L'application sera disponible sur:
# - Backend API: http://ai-OPCP:8000
# - Documentation API: http://OPCP:8000/docs
# - Frontend: http://OPCP:5173
```

### Arrêt

```bash
# Arrêter tous les services
docker-compose down

# Arrêter et supprimer les volumes (⚠️ supprime la base de données)
docker-compose down -v
```

## 🔧 Démarrage en Développement Local

### Backend

```bash
# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos paramètres

# Appliquer les migrations
alembic upgrade head

# Démarrer le serveur
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend disponible sur: http://ai-OPCP:8000

### Frontend

```bash
cd frontend

# Installer les dépendances
npm install

# Configurer l'API
cp .env.example .env
# Vérifier que VITE_API_BASE_URL=http://ai-OPCP:8000/api

# Démarrer le serveur de développement
npm run dev
```

Frontend disponible sur: http://frontend:5173

## 📝 Configuration

### Variables d'Environnement Essentielles

Le fichier `.env` contient déjà des valeurs par défaut pour le développement. Voici les variables importantes :

```env
# Base de données (requis)
DATABASE_URL=postgresql://user:password@postgres:5432/OPCP_db

# Sécurité (requis)
SECRET_KEY=your-secret-key-change-in-production

# Email (optionnel en dev, requis en production)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@OPCP.org

# Paiements (optionnel en dev, requis en production)
STRIPE_API_KEY=sk_test_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_secret
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_CLIENT_SECRET=your_client_secret
```

### Configuration Email (Production)

Pour activer l'envoi d'emails en production :

1. **Gmail** :
   - Activer l'authentification à 2 facteurs
   - Générer un mot de passe d'application
   - Utiliser : `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`

2. **SendGrid** :
   - Créer un compte SendGrid
   - Générer une clé API
   - Utiliser : `SMTP_HOST=smtp.sendgrid.net`, `SMTP_USER=apikey`

3. **Mailgun** :
   - Créer un compte Mailgun
   - Utiliser les credentials SMTP fournis

### Configuration Paiements (Production)

1. **Stripe** :
   - Créer un compte sur https://stripe.com
   - Récupérer les clés API (Dashboard > Developers > API keys)
   - Configurer les webhooks pour `/api/payments/stripe/webhook`

2. **PayPal** :
   - Créer un compte développeur sur https://developer.paypal.com
   - Créer une application REST API
   - Récupérer Client ID et Secret
   - Passer en mode `live` en production

## 🧪 Tests

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Lancer tous les tests
pytest

# Lancer avec couverture
pytest --cov=app tests/

# Lancer un test spécifique
pytest tests/test_auth.py -v
```

## 📚 Documentation API

Une fois le backend démarré, accédez à :

- **Swagger UI** : http://ai-OPCP:8000/docs
- **ReDoc** : http://ai-OPCP:8000/redoc

## 🔐 Compte Administrateur Initial

Pour créer le premier compte administrateur :

```bash
# Se connecter au conteneur
docker-compose exec app python

# Dans le shell Python
from app.database import SessionLocal
from app.models import User, UserRole
from app.auth.password import hash_password

db = SessionLocal()
admin = User(
    email="admin@opcp-psmc.com",
    password_hash=hash_password("Admin1234!"),
    first_name="Admin",
    last_name="OPCP",
    role=UserRole.ADMINISTRATOR,
    is_email_verified=True
)
db.add(admin)
db.commit()
print("✅ Administrateur créé : admin@opcp-psmc.com / Admin1234!")
```

## 🐛 Dépannage

### Erreur : "Field required" au démarrage

**Solution** : Le fichier `.env` est manquant ou incomplet.
```bash
cp .env.example .env
# Éditer .env avec vos valeurs
```

### Erreur : "Connection refused" (base de données)

**Solution** : PostgreSQL n'est pas démarré.
```bash
# Avec Docker
docker-compose up -d db

# Ou installer PostgreSQL localement
sudo systemctl start postgresql
```

### Erreur : "Module not found"

**Solution** : Dépendances manquantes.
```bash
pip install -r requirements.txt
```

### Frontend ne se connecte pas au backend

**Solution** : Vérifier la configuration CORS et l'URL de l'API.
```bash
# Dans frontend/.env
VITE_API_BASE_URL=http://ai-OPCP:8000/api

# Dans backend .env
ALLOWED_ORIGINS=http://ai-OPCP:5173,http://ai-OPCP:3000
```

## 📦 Structure du Projet

```
ai-OPCP/
├── app/                    # Code backend FastAPI
│   ├── auth/              # Authentification
│   ├── forum/             # Forum
│   ├── payments/          # Paiements
│   ├── documents/         # Documents
│   ├── events/            # Événements
│   ├── admin/             # Administration
│   └── main.py            # Point d'entrée
├── frontend/              # Code frontend React
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
├── tests/                 # Tests backend
├── migrations/            # Migrations Alembic
├── docs/                  # Documentation
├── docker-compose.yml     # Configuration Docker
├── .env                   # Variables d'environnement
└── requirements.txt       # Dépendances Python
```

## 🌐 URLs Importantes

- **Backend API** : http://ai-OPCP:8000
- **API Docs (Swagger)** : http://ai-OPCP:8000/docs
- **API Docs (ReDoc)** : http://ai-OPCP:8000/redoc
- **Frontend** : http://frontend:5173
- **Base de données** : ai-hypostgrespervisia:5432

## 📞 Support

Pour toute question ou problème :
- Consulter la documentation complète dans `/docs`
- Vérifier les logs : `docker-compose logs -f`
- Consulter le README principal

---

**PSMC OPCP** - OVH
