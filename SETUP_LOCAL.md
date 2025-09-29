# Guide de Démarrage Local avec Docker

## Prérequis

- Docker Desktop installé et en cours d'exécution
- Docker Compose (inclus avec Docker Desktop)
- Git pour cloner le projet

## Installation et Démarrage

### 1. Cloner le projet (si ce n'est pas déjà fait)

```bash
git clone <repository-url>
cd scorpiusProject
```

### 2. Démarrer l'environnement complet

```bash
# Démarrer tous les services (PostgreSQL, Redis, API, pgAdmin)
docker-compose up -d

# Vérifier que tous les conteneurs sont démarrés
docker-compose ps
```

### 3. Initialiser la base de données

```bash
# Redémarrer le service pour monter le volume scripts/
docker-compose restart app

# Exécuter le script d'initialisation pour créer toutes les tables
docker-compose exec app python scripts/init_db_complete.py
```

### 4. Vérifier que l'application fonctionne

```bash
# Tester le health check
curl http://localhost:8000/health

# Accéder à la documentation interactive
# Ouvrir dans votre navigateur: http://localhost:8000/api/v1/docs
```

## Services Disponibles

| Service | URL | Credentials |
|---------|-----|-------------|
| API FastAPI | <http://localhost:8000> | - |
| Health Check | <http://localhost:8000/health> | - |
| Documentation Swagger | <http://localhost:8000/api/v1/docs> | - |
| Documentation ReDoc | <http://localhost:8000/api/v1/redoc> | - |
| OpenAPI JSON | <http://localhost:8000/api/v1/openapi.json> | - |
| pgAdmin | <http://localhost:5050> | <admin@scorpiusproject.fr> / admin |
| PostgreSQL | localhost:5432 | scorpius / scorpius |
| Redis | localhost:6379 | - |

## Commandes Utiles

### Gestion des services

```bash
# Arrêter tous les services
docker-compose down

# Redémarrer un service spécifique
docker-compose restart app

# Voir les logs en temps réel
docker-compose logs -f app

# Voir les logs de tous les services
docker-compose logs -f
```

### Accès à la base de données

```bash
# Via psql dans le conteneur
docker-compose exec -e PGPASSWORD=scorpius db psql -U scorpius -d scorpius_mvp

# Lister toutes les tables
docker-compose exec -e PGPASSWORD=scorpius db psql -U scorpius -d scorpius_mvp -c "\dt"

# Vérifier les utilisateurs
docker-compose exec -e PGPASSWORD=scorpius db psql -U scorpius -d scorpius_mvp -c "SELECT id, email, created_at FROM users;"

# Depuis votre machine locale (hôte)
PGPASSWORD=scorpius psql -h localhost -p 5432 -U scorpius -d scorpius_mvp
```

### Accès au conteneur API

```bash
# Ouvrir un shell dans le conteneur API
docker-compose exec app bash

# Exécuter des commandes Python
docker-compose exec app python -c "print('Hello')"

# Lancer les tests
docker-compose exec app pytest tests/unit -v
```

### Nettoyage complet

```bash
# Arrêter et supprimer tous les conteneurs, volumes et réseaux
docker-compose down -v

# Rebuild complet (après modification du Dockerfile)
docker-compose up -d --build
```

## Tester l'API

### 1. Créer un compte utilisateur

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass1!",
    "full_name": "Test User"
  }'
```

### 2. Se connecter

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass1!"
  }'
```

Copier le `access_token` retourné.

### 3. Accéder à un endpoint protégé

```bash
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

## Résolution de Problèmes

### Les conteneurs ne démarrent pas

```bash
# Vérifier les logs d'erreur
docker-compose logs

# Vérifier que les ports ne sont pas déjà utilisés
lsof -i :8000  # API
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
```

### La base de données n'a pas de tables

```bash
# Réinitialiser complètement la base de données
docker-compose down -v
docker-compose up -d
docker-compose exec api python scripts/init_db_complete.py
```

### Hot-reload ne fonctionne pas

```bash
# Vérifier que le volume est bien monté
docker-compose exec api ls -la /app/src

# Redémarrer le service API
docker-compose restart api
```

### Erreur "Password should not contain sequential characters"

Utiliser un mot de passe plus simple et conforme:

- ✅ `TestPass1!`
- ✅ `MySecure2024!`
- ❌ `TestPassword123!` (trop de caractères séquentiels)

## Configuration de pgAdmin

1. Ouvrir <http://localhost:5050>
2. Login: `admin@scorpius.fr` / `admin`
3. Ajouter un nouveau serveur:
   - Name: `Scorpius Local`
   - Host: `postgres` (nom du service Docker)
   - Port: `5432`
   - Database: `scorpius_dev`
   - Username: `scorpius`
   - Password: `scorpius123`

## Scripts Utiles

### Script de test complet de l'environnement

Le script `start_test_environment.sh` permet de démarrer et tester automatiquement l'environnement:

```bash
./start_test_environment.sh
```

Ce script:

- Démarre tous les services Docker
- Initialise la base de données
- Teste l'inscription et la connexion
- Affiche un rapport complet

## Variables d'Environnement

Les variables d'environnement sont définies dans `docker-compose.yml`:

```yaml
DATABASE_URL: postgresql+asyncpg://scorpius:scorpius123@postgres:5432/scorpius_dev
REDIS_URL: redis://redis:6379/0
JWT_SECRET: your-secret-key-change-in-production
```

Pour l'environnement de production, ces variables sont définies dans `docker-compose.prod.yml` et doivent être sécurisées.

## Développement

### Structure des volumes

Le code source et les scripts sont montés en volume pour permettre le hot-reload:

```yaml
volumes:
  - ./src:/app/src        # Code source
  - ./scripts:/app/scripts  # Scripts d'initialisation
  - ./uploads:/app/uploads  # Fichiers uploadés
  - ./logs:/app/logs       # Logs de l'application
```

Les modifications dans `src/` et `scripts/` sont immédiatement prises en compte sans redémarrage ni rebuild.

### Lancer les tests

```bash
# Tests unitaires
docker-compose exec api pytest tests/unit -v

# Tests d'intégration
docker-compose exec api pytest tests/integration -v

# Tous les tests avec couverture
docker-compose exec api pytest --cov=src --cov-report=html
```

### Vérifier la qualité du code

```bash
# Linting
docker-compose exec api ruff check src tests

# Type checking
docker-compose exec api mypy src

# Security scan
docker-compose exec api bandit -r src
```
