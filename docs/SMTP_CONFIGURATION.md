# Configuration SMTP pour l'envoi d'emails

## Vue d'ensemble

L'application OPCP utilise SMTP pour envoyer des emails de confirmation lors de l'inscription des utilisateurs, ainsi que pour d'autres notifications.

## Variables d'environnement

Les paramètres SMTP sont configurés via les variables d'environnement dans le fichier `.env` :

```env
# Email Configuration (SMTP)
SMTP_HOST=smtp.example.com          # Serveur SMTP (ex: smtp.gmail.com, smtp.office365.com)
SMTP_PORT=587                        # Port SMTP (587 pour TLS, 465 pour SSL)
SMTP_USER=your-email@example.com    # Nom d'utilisateur SMTP (généralement votre email)
SMTP_PASSWORD=your-email-password   # Mot de passe SMTP ou mot de passe d'application
SMTP_FROM=noreply@OPCP.org    # Adresse email d'expédition
```

## Valeurs par défaut

Si les variables ne sont pas définies, les valeurs par défaut suivantes sont utilisées (définies dans `app/config.py`) :

- **SMTP_HOST**: `localhost`
- **SMTP_PORT**: `587`
- **SMTP_USER**: `""` (vide)
- **SMTP_PASSWORD**: `""` (vide)
- **SMTP_FROM**: `noreply@OPCP.org`

## Exemples de configuration

### Gmail

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-mot-de-passe-application
SMTP_FROM=noreply@OPCP.org
```

**Note importante pour Gmail**: Vous devez créer un "mot de passe d'application" dans les paramètres de sécurité de votre compte Google :
1. Allez dans votre compte Google → Sécurité
2. Activez la validation en deux étapes
3. Créez un mot de passe d'application
4. Utilisez ce mot de passe dans `SMTP_PASSWORD`

### Office 365 / Outlook

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=votre-email@outlook.com
SMTP_PASSWORD=votre-mot-de-passe
SMTP_FROM=noreply@OPCP.org
```

### OVH

```env
SMTP_HOST=ssl0.ovh.net
SMTP_PORT=587
SMTP_USER=votre-email@votredomaine.com
SMTP_PASSWORD=votre-mot-de-passe
SMTP_FROM=noreply@OPCP.org
```

### SendGrid

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=votre-api-key-sendgrid
SMTP_FROM=noreply@OPCP.org
```

### Mailgun

```env
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@votredomaine.mailgun.org
SMTP_PASSWORD=votre-mot-de-passe-mailgun
SMTP_FROM=noreply@OPCP.org
```

## Fonctionnalités email

### 1. Email de vérification (Registration)

Lors de l'inscription d'un utilisateur, un email de vérification est automatiquement envoyé avec :
- Un lien de vérification contenant un token JWT
- Validité du token : 24 heures
- Template HTML et texte brut

**Code source**: `app/auth/router.py` (fonction `register`)

### 2. Autres notifications

Le service email peut également être utilisé pour :
- Notifications de forum (réponses aux sujets)
- Rappels d'événements
- Rappels d'adhésion
- Notifications personnalisées

**Code source**: `app/services/email.py`

## Test de la configuration

Pour tester votre configuration SMTP, vous pouvez :

1. **Créer un compte de test** via l'endpoint `/api/auth/register`
2. **Vérifier les logs** dans la console pour voir si l'email a été envoyé
3. **Vérifier votre boîte email** pour recevoir l'email de confirmation

### Exemple de test avec curl

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test1234",
    "first_name": "Test",
    "last_name": "User"
  }'
```

## Dépannage

### L'email n'est pas envoyé

1. **Vérifiez les logs** : Les erreurs SMTP sont enregistrées dans les logs de l'application
2. **Vérifiez les credentials** : Assurez-vous que `SMTP_USER` et `SMTP_PASSWORD` sont corrects
3. **Vérifiez le port** : 
   - Port 587 : TLS (recommandé)
   - Port 465 : SSL
   - Port 25 : Non sécurisé (non recommandé)
4. **Vérifiez le pare-feu** : Assurez-vous que le port SMTP n'est pas bloqué
5. **Vérifiez les limites d'envoi** : Certains fournisseurs limitent le nombre d'emails par jour

### Erreur "Authentication failed"

- Vérifiez que vous utilisez le bon mot de passe (mot de passe d'application pour Gmail)
- Vérifiez que l'authentification à deux facteurs est configurée si nécessaire
- Vérifiez que le compte n'est pas verrouillé

### Erreur "Connection refused"

- Vérifiez que `SMTP_HOST` et `SMTP_PORT` sont corrects
- Vérifiez que votre serveur peut accéder au serveur SMTP (pas de pare-feu)

## Mode développement

En développement, si vous n'avez pas de serveur SMTP configuré :

1. **Option 1 : Utiliser un service de test**
   - [Mailtrap](https://mailtrap.io/) - Service de test d'emails gratuit
   - [MailHog](https://github.com/mailhog/MailHog) - Serveur SMTP local pour tests

2. **Option 2 : Désactiver temporairement**
   - L'inscription fonctionnera toujours
   - L'email ne sera pas envoyé (erreur loggée mais non bloquante)
   - Vous pouvez vérifier manuellement les comptes dans la base de données

### Configuration Mailtrap (recommandé pour dev)

```env
SMTP_HOST=smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=votre-username-mailtrap
SMTP_PASSWORD=votre-password-mailtrap
SMTP_FROM=noreply@OPCP.org
```

## Sécurité

⚠️ **Important** :
- Ne commitez JAMAIS le fichier `.env` dans Git
- Utilisez des mots de passe d'application plutôt que vos mots de passe principaux
- En production, utilisez des variables d'environnement sécurisées
- Limitez les permissions du fichier `.env` : `chmod 600 .env`

## Production

Pour la production, il est recommandé d'utiliser :
- Un service d'email transactionnel (SendGrid, Mailgun, AWS SES)
- Des variables d'environnement système plutôt qu'un fichier `.env`
- Un domaine vérifié pour `SMTP_FROM`
- DKIM et SPF configurés pour éviter le spam

## Support

Pour plus d'informations :
- Documentation FastAPI : https://fastapi.tiangolo.com/
- Documentation Python smtplib : https://docs.python.org/3/library/smtplib.html
