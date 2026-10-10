# Test Rapide SMTP - Configuration Gandi

## 🚀 Test en 3 étapes

### Étape 1 : Configurer le fichier .env

Éditez le fichier `.env` et ajoutez :

```env
SMTP_HOST=mail.gandi.net
SMTP_PORT=587
SMTP_USER=admin@opcp-psmc.com
SMTP_PASSWORD=VOTRE_VRAI_MOT_DE_PASSE
SMTP_FROM=noreply@opcp-psmc.com
```

⚠️ Remplacez `VOTRE_VRAI_MOT_DE_PASSE` par le vrai mot de passe !

### Étape 2 : Tester avec le script

**Option A - Script Python simple** :
```bash
# Éditez le script et mettez le vrai mot de passe
nano test_email.py

# Exécutez le script
python test_email.py
```

**Option B - Script intégré à l'application** :
```bash
# Depuis le conteneur Docker
docker-compose exec backend python app/test_smtp.py

# Ou en local
python app/test_smtp.py
```

### Étape 3 : Vérifier l'email

Vérifiez la boîte email `lepetre@yahoo.fr` :
- ✅ Boîte de réception
- ⚠️ Dossier spam/courrier indésirable

## 📋 Checklist de vérification

Avant de tester, vérifiez que :

- [ ] Le compte `admin@opcp-psmc.com` existe sur Gandi
- [ ] Le mot de passe est correct
- [ ] L'accès SMTP est activé sur Gandi
- [ ] Le port 587 n'est pas bloqué par un pare-feu
- [ ] Le fichier `.env` est bien configuré

## 🔧 Test de connexion rapide

Testez la connexion au serveur SMTP :

```bash
telnet mail.gandi.net 587
```

Si la connexion réussit, vous verrez :
```
Trying 217.70.177.40...
Connected to mail.gandi.net.
220 mail.gandi.net ESMTP
```

Tapez `QUIT` pour quitter.

## 📝 Test via l'API

Une fois configuré, testez l'inscription :

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "lepetre@yahoo.fr",
    "password": "Test1234",
    "first_name": "Test",
    "last_name": "User"
  }'
```

Vérifiez les logs :
```bash
docker-compose logs -f backend | grep -i email
```

## ❓ Problèmes courants

### "Authentication failed"
→ Vérifiez le mot de passe dans le panneau Gandi

### "Connection refused"
→ Vérifiez que le port 587 n'est pas bloqué

### Email non reçu
→ Vérifiez le dossier spam de Yahoo

### "Relay access denied"
→ Vérifiez que `admin@opcp-psmc.com` existe sur Gandi

## 📚 Documentation complète

Pour plus de détails, consultez :
- `TEST_EMAIL_INSTRUCTIONS.md` - Instructions détaillées
- `docs/SMTP_CONFIGURATION.md` - Configuration complète
