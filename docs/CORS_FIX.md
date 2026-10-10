# Correction de l'erreur CORS pour Oracle AI

## Problème identifié

L'erreur CORS se produisait lors de l'accès à la page Oracle AI :

```
Blocage d'une requête multiorigine (Cross-Origin Request) : 
la politique « Same Origin » ne permet pas de consulter la ressource distante 
située sur https://ai-OPCP:8000/api/oracle/ask. 
Raison : échec de la requête CORS. Code d'état : (null).
```

## Cause du problème

Le service `oracleService.ts` utilisait directement `axios` avec une URL absolue (`https://ai-OPCP:8000`) au lieu d'utiliser l'instance `api` configurée qui gère automatiquement :
- Les URLs relatives (`/api`)
- Les en-têtes d'authentification
- Les intercepteurs de requêtes/réponses
- La gestion des erreurs

## Solution appliquée

### 1. Modification du service Oracle

**Avant** :
```typescript
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'https://ai-OPCP:8000';

async askOracle(query: OracleQuery): Promise<OracleResponse> {
  const response = await axios.post(
    `${API_URL}/api/oracle/ask`,
    query,
    { headers: this.getAuthHeader() }
  );
  return response.data;
}
```

**Après** :
```typescript
import api from './api';

async askOracle(query: OracleQuery): Promise<OracleResponse> {
  const response = await api.post('/oracle/ask', query);
  return response.data;
}
```

### 2. Avantages de cette approche

- ✅ Utilise l'instance `api` configurée avec les bons paramètres
- ✅ Gère automatiquement l'authentification via les intercepteurs
- ✅ Utilise des URLs relatives qui passent par le proxy Nginx
- ✅ Évite les problèmes CORS en utilisant le même domaine
- ✅ Gestion centralisée des erreurs (redirection 401, etc.)
- ✅ Timeout configuré (30 secondes)

## Configuration CORS côté backend

La configuration CORS dans `app/main.py` est correcte :

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Variables d'environnement

Dans le fichier `.env`, assurez-vous que `ALLOWED_ORIGINS` inclut toutes les origines nécessaires :

```env
# Pour le développement
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:6003,http://ai-OPCP:8000,https://ai-OPCP:8000

# Pour la production
ALLOWED_ORIGINS=https://opcp-psmc.com,https://www.opcp-psmc.com
```

## Architecture de proxy

Le frontend utilise Nginx comme proxy inverse pour éviter les problèmes CORS :

```
Frontend (React) → Nginx → Backend (FastAPI)
http://localhost:3000 → /api → http://backend:8000/api
```

Cette architecture permet :
- Pas de problèmes CORS (même domaine)
- Gestion centralisée des requêtes
- Possibilité de load balancing
- Meilleure sécurité

## Configuration Nginx

Le fichier `frontend/nginx.conf` contient la configuration du proxy :

```nginx
location /api {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Vérification

Pour vérifier que la correction fonctionne :

1. **Redémarrez l'application** :
   ```bash
   docker-compose restart frontend
   ```

2. **Accédez à la page Oracle AI** :
   ```
   http://localhost:3000/oracle
   ```

3. **Ouvrez la console du navigateur** (F12) et vérifiez :
   - Onglet "Réseau" : Les requêtes vers `/api/oracle/ask` doivent réussir (200 OK)
   - Onglet "Console" : Aucune erreur CORS ne doit apparaître

4. **Testez une question** :
   - Posez une question à l'Oracle
   - Vérifiez que la réponse s'affiche correctement

## Autres services à vérifier

Si d'autres services ont le même problème, appliquez la même correction :

### ❌ Mauvaise pratique
```typescript
import axios from 'axios';
const API_URL = 'https://ai-OPCP:8000';
axios.post(`${API_URL}/api/endpoint`, data);
```

### ✅ Bonne pratique
```typescript
import api from './api';
api.post('/endpoint', data);
```

## Services déjà corrigés

- ✅ `authService.ts` - Utilise `api`
- ✅ `forumService.ts` - Utilise `api`
- ✅ `adminService.ts` - Utilise `api`
- ✅ `oracleService.ts` - **Corrigé** - Utilise maintenant `api`

## Dépannage

### Erreur CORS persiste après la correction

1. **Videz le cache du navigateur** :
   - Chrome : Ctrl+Shift+Delete
   - Firefox : Ctrl+Shift+Delete
   - Ou utilisez le mode navigation privée

2. **Vérifiez la configuration Nginx** :
   ```bash
   docker-compose exec frontend cat /etc/nginx/nginx.conf
   ```

3. **Vérifiez les logs** :
   ```bash
   # Logs frontend
   docker-compose logs -f frontend
   
   # Logs backend
   docker-compose logs -f backend
   ```

### Erreur 401 Unauthorized

Si vous obtenez une erreur 401, vérifiez :
- Le token est bien stocké dans `localStorage`
- Le token n'est pas expiré
- L'intercepteur d'authentification fonctionne

### Erreur de connexion

Si la requête ne passe pas du tout :
- Vérifiez que le backend est démarré : `docker-compose ps`
- Vérifiez que Nginx est configuré correctement
- Vérifiez les logs Nginx : `docker-compose logs nginx`

## Bonnes pratiques

1. **Toujours utiliser l'instance `api` configurée** pour les requêtes backend
2. **Utiliser des URLs relatives** (`/api/endpoint` au lieu de `http://...`)
3. **Configurer CORS correctement** côté backend pour les cas où c'est nécessaire
4. **Utiliser un proxy Nginx** en production pour éviter les problèmes CORS
5. **Tester en mode navigation privée** pour éviter les problèmes de cache

## Références

- [MDN - CORS](https://developer.mozilla.org/fr/docs/Web/HTTP/CORS)
- [FastAPI - CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [Axios - Interceptors](https://axios-http.com/docs/interceptors)
