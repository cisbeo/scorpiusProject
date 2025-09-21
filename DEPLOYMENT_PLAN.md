# Plan de Déploiement - Scorpius Project MVP

## 🎯 Objectif
Déployer le backend Scorpius MVP en environnement de production pour les tests utilisateurs et la validation fonctionnelle.

## 📋 Vue d'ensemble du déploiement

### Architecture cible
```
Internet → Load Balancer → FastAPI App → PostgreSQL
                       ↘ Redis Cache
                       ↘ File Storage
```

## 🔧 Infrastructure requise

### 1. Serveur Application
- **Spécifications minimales**: 2 CPU, 4GB RAM, 50GB SSD
- **OS recommandé**: Ubuntu 22.04 LTS
- **Services**: Docker, Docker Compose
- **Ports**: 80 (HTTP), 443 (HTTPS), 8000 (API)

### 2. Base de données PostgreSQL
- **Version**: PostgreSQL 15+
- **Spécifications**: 2 CPU, 4GB RAM, 100GB SSD
- **Extensions**: pgvector (pour futures fonctionnalités ML)
- **Backup**: Snapshots quotidiens

### 3. Cache Redis
- **Version**: Redis 7+
- **Spécifications**: 1 CPU, 2GB RAM
- **Persistence**: RDB + AOF

### 4. Stockage fichiers
- **Type**: Volume persistant ou S3-compatible
- **Capacité**: 500GB minimum
- **Sécurité**: Chiffrement at-rest

## 🐳 Configuration Docker

### Dockerfile de production
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application
COPY src/ ./src/
COPY main.py alembic.ini ./

# Create non-root user
RUN useradd -m -u 1000 scorpius && chown -R scorpius:scorpius /app
USER scorpius

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### docker-compose.prod.yml
```yaml
version: '3.8'

services:
  api:
    build: .
    container_name: scorpius-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql://scorpius:${DB_PASSWORD}@postgres:5432/scorpius_prod
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - scorpius-network

  postgres:
    image: postgres:15
    container_name: scorpius-db
    restart: unless-stopped
    environment:
      - POSTGRES_DB=scorpius_prod
      - POSTGRES_USER=scorpius
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"
    networks:
      - scorpius-network

  redis:
    image: redis:7-alpine
    container_name: scorpius-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - scorpius-network

  nginx:
    image: nginx:alpine
    container_name: scorpius-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api
    networks:
      - scorpius-network

volumes:
  postgres_data:
  redis_data:

networks:
  scorpius-network:
    driver: bridge
```

## ⚙️ Configuration de production

### 1. Variables d'environnement (.env.prod)
```bash
# Application
APP_ENV=production
APP_NAME=ScorpiusProject
DEBUG=false
LOG_LEVEL=INFO

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database
DATABASE_URL=postgresql://scorpius:${DB_PASSWORD}@postgres:5432/scorpius_prod
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50

# Security
JWT_SECRET_KEY=${JWT_SECRET_KEY}
SECRET_KEY=${SECRET_KEY}
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["https://votre-domaine.fr"]

# File Upload
MAX_UPLOAD_SIZE=104857600
UPLOAD_PATH=/app/uploads
TEMP_PATH=/tmp/scorpius

# Email (optionnel)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@votre-domaine.fr
SMTP_PASSWORD=${SMTP_PASSWORD}
```

### 2. Configuration Nginx
```nginx
upstream scorpius_api {
    server api:8000;
}

server {
    listen 80;
    server_name votre-domaine.fr;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name votre-domaine.fr;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://scorpius_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://scorpius_api/health;
        access_log off;
    }
}
```

## 🚀 Procédure de déploiement

### Phase 1: Préparation de l'environnement

#### 1.1 Configuration du serveur
```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Installation Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 1.2 Préparation des répertoires
```bash
mkdir -p /opt/scorpius/{uploads,logs,backups,ssl}
cd /opt/scorpius
```

#### 1.3 Génération des secrets
```bash
# Génération JWT secret
openssl rand -hex 32

# Génération app secret
openssl rand -hex 32

# Génération mot de passe DB
openssl rand -base64 32
```

### Phase 2: Déploiement de l'application

#### 2.1 Clonage et préparation
```bash
git clone https://github.com/votre-org/scorpius-project.git
cd scorpius-project
```

#### 2.2 Configuration de l'environnement
```bash
# Création du fichier d'environnement
cp .env.example .env.prod
# Éditer .env.prod avec les valeurs générées
```

#### 2.3 Construction et lancement
```bash
# Construction des images
docker-compose -f docker-compose.prod.yml build

# Lancement des services
docker-compose -f docker-compose.prod.yml up -d
```

### Phase 3: Initialisation de la base de données

#### 3.1 Migrations
```bash
# Attendre que PostgreSQL soit prêt
docker-compose -f docker-compose.prod.yml exec api python -c "
import asyncio
from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Database initialized')

asyncio.run(init_db())
"
```

#### 3.2 Création utilisateur admin (optionnel)
```bash
docker-compose -f docker-compose.prod.yml exec api python -c "
import asyncio
from src.services.auth.auth_service import AuthService
from src.db.session import get_async_db

async def create_admin():
    async for db in get_async_db():
        auth_service = AuthService(db)
        await auth_service.register_user(
            email='admin@votre-domaine.fr',
            password='MotDePasseSecurise123!',
            full_name='Administrateur',
            role='admin'
        )
        print('Admin user created')
        break

asyncio.run(create_admin())
"
```

## 🔍 Tests de validation

### 1. Tests de santé
```bash
# Test de l'API
curl -X GET https://votre-domaine.fr/health

# Test des endpoints principaux
curl -X GET https://votre-domaine.fr/api/v1/docs
```

### 2. Tests fonctionnels
```bash
# Test d'enregistrement
curl -X POST https://votre-domaine.fr/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!",
    "full_name": "Utilisateur Test",
    "role": "bid_manager"
  }'

# Test de connexion
curl -X POST https://votre-domaine.fr/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!"
  }'
```

## 📊 Monitoring et observabilité

### 1. Métriques système
```bash
# Script de monitoring
#!/bin/bash
echo "=== Scorpius System Status ==="
docker-compose -f docker-compose.prod.yml ps
echo ""
echo "=== API Health ==="
curl -s https://votre-domaine.fr/health | jq '.'
echo ""
echo "=== Database Status ==="
docker-compose -f docker-compose.prod.yml exec postgres pg_isready
echo ""
echo "=== Disk Usage ==="
df -h /opt/scorpius
```

### 2. Logs centralisés
```bash
# Consultation des logs
docker-compose -f docker-compose.prod.yml logs -f api

# Logs avec rotation
echo '{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  }
}' | sudo tee /etc/docker/daemon.json
```

## 🔒 Sécurité

### 1. Certificats SSL
```bash
# Avec Let's Encrypt (Certbot)
sudo snap install --classic certbot
sudo certbot certonly --standalone -d votre-domaine.fr
sudo cp /etc/letsencrypt/live/votre-domaine.fr/* /opt/scorpius/ssl/
```

### 2. Firewall
```bash
# Configuration UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Backup automatique
```bash
# Script de sauvegarde
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U scorpius scorpius_prod > /opt/scorpius/backups/backup_$DATE.sql
find /opt/scorpius/backups -name "backup_*.sql" -mtime +7 -delete
```

## 📅 Planning de déploiement

### Semaine 1: Préparation
- [ ] Provision des serveurs
- [ ] Configuration DNS
- [ ] Génération des certificats SSL
- [ ] Tests de l'infrastructure

### Semaine 2: Déploiement
- [ ] Installation des services
- [ ] Configuration de l'application
- [ ] Tests fonctionnels
- [ ] Formation des utilisateurs

### Semaine 3: Tests utilisateurs
- [ ] Tests d'acceptation
- [ ] Correction des bugs identifiés
- [ ] Optimisations de performance
- [ ] Documentation finale

## ⚠️ Points d'attention

### Critiques
1. **Sauvegarde**: Backup automatique quotidien obligatoire
2. **Monitoring**: Surveillance continue de la santé du système
3. **Sécurité**: Mise à jour régulière des dépendances
4. **Performance**: Monitoring des métriques de performance

### Nice-to-have
1. **CDN**: Pour les fichiers statiques
2. **Load balancer**: Pour la haute disponibilité
3. **Monitoring avancé**: Prometheus + Grafana
4. **CI/CD**: Pipeline de déploiement automatisé

## 📞 Support et maintenance

### Contacts d'urgence
- **Développeur principal**: [contact]
- **Admin système**: [contact]
- **Responsable métier**: [contact]

### Procédures d'urgence
1. **Arrêt d'urgence**: `docker-compose -f docker-compose.prod.yml down`
2. **Restauration**: Script de restore depuis backup
3. **Rollback**: Retour à la version précédente

---

**✅ Plan validé pour déploiement en production**

Ce plan couvre tous les aspects critiques pour un déploiement sécurisé et fiable du système Scorpius en production.