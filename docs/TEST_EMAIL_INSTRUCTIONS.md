# Instructions pour tester l'envoi d'email

## Configuration Gandi

Vous avez fourni la configuration suivante :
```env
SMTP_HOST=mail.gandi.net
SMTP_PORT=587
SMTP_USER=admin@opcp-psmc.com
SMTP_PASSWORD=your-email-password
SMTP_FROM=noreply@opcp-psmc.com
```

## Étape 1 : Mettre à jour le fichier .env

Éditez le fichier `.env` à la racine du projet et ajoutez/modifiez ces lignes :

```env
SMTP_HOST=mail.gandi.net
SMTP_PORT=587
SMTP_USER=admin@opcp-psmc.com
SMTP_PASSWORD=VOTRE_VRAI_MOT_DE_PASSE_ICI
SMTP_FROM=noreply@opcp-psmc.com
```

⚠️ **Important** : Remplacez `VOTRE_VRAI_MOT_DE_PASSE_ICI` par le vrai mot de passe du compte email.

## Étape 2 : Tester avec le script Python

J'ai créé un script de test `test_email.py`. Pour l'utiliser :

1. **Modifiez le mot de passe dans le script** :
   ```bash
   nano test_email.py
   # Remplacez "your-email-password" par le vrai mot de passe
   ```

2. **Exécutez le script** :
   ```bash
   python test_email.py
   ```

Le script va :
- Se connecter au serveur SMTP Gandi
- Envoyer un email de test à lepetre@yahoo.fr
- Afficher les détails de la connexion et les erreurs éventuelles

## Étape 3 : Tester via l'application

Une fois le fichier `.env` configuré, testez l'inscription :

1. **Redémarrez l'application** pour charger la nouvelle configuration :
   ```bash
   docker-compose restart
   ```

2. **Créez un compte de test** :
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

3. **Vérifiez les logs** :
   ```bash
   docker-compose logs -f backend
   ```

4. **Vérifiez l'email** dans la boîte lepetre@yahoo.fr (et le dossier spam)

## Vérifications importantes pour Gandi

### 1. Vérifier que le compte email existe

Connectez-vous à votre panneau Gandi et vérifiez que :
- Le compte `admin@opcp-psmc.com` existe
- Le mot de passe est correct
- L'accès SMTP est activé

### 2. Configuration DNS

Pour éviter que les emails soient marqués comme spam, vérifiez que :
- Les enregistrements SPF sont configurés
- Les enregistrements DKIM sont configurés (si disponible)

Exemple d'enregistrement SPF pour Gandi :
```
v=spf1 include:_mailcust.gandi.net ~all
```

### 3. Limites d'envoi

Gandi peut avoir des limites d'envoi. Vérifiez :
- Limite quotidienne d'emails
- Limite horaire d'emails

## Dépannage

### Erreur "Authentication failed"

**Causes possibles** :
- Mot de passe incorrect
- Compte email n'existe pas
- Authentification SMTP désactivée

**Solutions** :
1. Vérifiez le mot de passe dans le panneau Gandi
2. Réinitialisez le mot de passe si nécessaire
3. Vérifiez que l'accès SMTP est activé

### Erreur "Connection refused" ou "Timeout"

**Causes possibles** :
- Pare-feu bloquant le port 587
- Serveur SMTP inaccessible
- Problème réseau

**Solutions** :
1. Testez la connexion au serveur :
   ```bash
   telnet mail.gandi.net 587
   ```
2. Vérifiez votre pare-feu
3. Essayez depuis un autre réseau

### Email non reçu

**Vérifications** :
1. Vérifiez le dossier spam/courrier indésirable
2. Vérifiez les logs de l'application
3. Vérifiez les logs Gandi (si disponibles)
4. Attendez quelques minutes (délai de livraison)

### Email marqué comme spam

**Solutions** :
1. Configurez SPF et DKIM
2. Utilisez un domaine vérifié pour SMTP_FROM
3. Évitez les mots "spam" dans le sujet
4. Ajoutez un lien de désinscription

## Alternative : Utiliser un alias

Si `noreply@opcp-psmc.com` n'existe pas, vous pouvez :

1. **Option 1** : Créer l'alias dans Gandi
   - Créez un alias `noreply@opcp-psmc.com` → `admin@opcp-psmc.com`

2. **Option 2** : Utiliser directement admin@opcp-psmc.com
   ```env
   SMTP_FROM=admin@opcp-psmc.com
   ```

## Test rapide avec curl

Pour tester rapidement la connexion SMTP :

```bash
curl -v --url 'smtp://mail.gandi.net:587' \
  --mail-from 'admin@opcp-psmc.com' \
  --mail-rcpt 'lepetre@yahoo.fr' \
  --user 'admin@opcp-psmc.com:VOTRE_MOT_DE_PASSE' \
  --upload-file - << EOF
From: noreply@opcp-psmc.com
To: lepetre@yahoo.fr
Subject: Test SMTP

Ceci est un test.
EOF
```

## Support

Si vous rencontrez des problèmes :
1. Consultez la documentation Gandi : https://docs.gandi.net/fr/
2. Contactez le support Gandi
3. Vérifiez les logs de l'application : `docker-compose logs backend`

## Sécurité

⚠️ **Ne commitez jamais le fichier .env avec le vrai mot de passe !**

Le fichier `.env` est déjà dans `.gitignore`, mais vérifiez :
```bash
git status
# Le fichier .env ne doit PAS apparaître
```
