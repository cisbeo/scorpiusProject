# 🧪 Tests Locaux - Scorpius Project

## 🚀 Test rapide sur machine de développement (5 minutes)

### Option 1: Test avec SQLite (le plus simple)

#### 1. Installation des dépendances
```bash
# Depuis le dossier du projet
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### 2. Configuration locale
```bash
# Créer fichier d'environnement local
cp .env.prod.example .env.local

# Éditer .env.local
nano .env.local
```

#### 3. Contenu .env.local (SQLite)
```bash
# Application
APP_ENV=development
APP_NAME=ScorpiusProject
DEBUG=true
LOG_LEVEL=DEBUG

# Base de données locale (SQLite)
DATABASE_URL=sqlite+aiosqlite:///./test_scorpius.db

# Sécurité (clés de test)
JWT_SECRET_KEY=dev-jwt-secret-key-for-testing-only
SECRET_KEY=dev-app-secret-key-for-testing-only

# CORS local
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080","http://localhost:8000"]

# Upload local
MAX_UPLOAD_SIZE=52428800
UPLOAD_PATH=./uploads
TEMP_PATH=./temp
ALLOWED_EXTENSIONS=[".pdf"]
```

#### 4. Démarrage local
```bash
# Créer dossiers
mkdir -p uploads temp logs

# Initialiser base SQLite
python -c "
import asyncio
import os
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_scorpius.db'
from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('✅ Base SQLite initialisée')

asyncio.run(init_db())
"

# Démarrer l'API
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --env-file .env.local
```

#### 5. Test de l'API
```bash
# Dans un autre terminal
# Test santé
curl http://localhost:8000/health

# Test documentation
open http://localhost:8000/docs
```

---

### Option 2: Test avec Docker (plus proche production)

#### 1. Docker Compose de développement
```bash
# Créer docker-compose.dev.yml
cat > docker-compose.dev.yml << 'EOF'
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=development
      - DATABASE_URL=postgresql://scorpius:devpassword@postgres:5432/scorpius_dev
      - JWT_SECRET_KEY=dev-jwt-secret-key-for-testing-only
      - SECRET_KEY=dev-app-secret-key-for-testing-only
      - DEBUG=true
    volumes:
      - ./src:/app/src
      - ./uploads:/app/uploads
    depends_on:
      - postgres
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=scorpius_dev
      - POSTGRES_USER=scorpius
      - POSTGRES_PASSWORD=devpassword
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data

volumes:
  postgres_dev_data:
EOF

# Démarrage
docker-compose -f docker-compose.dev.yml up -d

# Initialisation base
docker-compose -f docker-compose.dev.yml exec api python -c "
import asyncio
from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('✅ Base PostgreSQL initialisée')

asyncio.run(init_db())
"
```

---

## 🧪 Tests Fonctionnels Complets

### 1. Tests automatisés
```bash
# Tests unitaires
pytest tests/unit -v

# Tests avec base SQLite
DATABASE_URL=sqlite+aiosqlite:///./test.db pytest tests/integration -v -k "not database"

# Tests contrats API
pytest tests/contract -v
```

### 2. Tests manuels avec curl

#### Enregistrement utilisateur
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!",
    "full_name": "Utilisateur Test",
    "role": "bid_manager"
  }'
```

#### Connexion
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!"
  }'

# Récupérer le token de la réponse
export TOKEN="votre_access_token_ici"
```

#### Upload document
```bash
# Créer un PDF de test
echo "%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000010 00000 n
0000000079 00000 n
0000000173 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
301
%%EOF" > test.pdf

# Upload
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf" \
  -F "title=Document Test"
```

#### Créer profil entreprise
```bash
curl -X POST http://localhost:8000/api/v1/company-profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Ma Société SARL",
    "siret": "12345678901234",
    "description": "Société de test",
    "capabilities_json": [
      {"name": "Développement Web", "keywords": ["Python", "FastAPI"]},
      {"name": "Consulting IT", "keywords": ["Architecture", "Cloud"]}
    ],
    "team_size": 10,
    "annual_revenue": 500000.0
  }'
```

### 3. Interface web de test

#### Swagger UI
```bash
# Ouvrir l'interface de test
open http://localhost:8000/docs
```

#### Test avec interface
1. Aller sur http://localhost:8000/docs
2. Cliquer sur "Try it out" pour chaque endpoint
3. Tester le workflow complet :
   - Register → Login → Upload → Process → Analyze

---

## 📊 Monitoring Local

### Logs en temps réel
```bash
# Logs API
tail -f logs/scorpius.log

# Logs uvicorn
# Les logs apparaissent directement dans le terminal
```

### Base de données
```bash
# SQLite
sqlite3 test_scorpius.db ".tables"
sqlite3 test_scorpius.db "SELECT * FROM users;"

# PostgreSQL (si Docker)
docker-compose -f docker-compose.dev.yml exec postgres psql -U scorpius -d scorpius_dev -c "\dt"
```

### Performances
```bash
# Test de charge simple
for i in {1..10}; do
  curl -s http://localhost:8000/health &
done
wait
```

---

## 🔧 Outils de Développement

### 1. Rechargement automatique
```bash
# L'API redémarre automatiquement avec --reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Débogage
```bash
# Mode debug avec prints
export DEBUG=true
python -c "
import asyncio
from src.api.v1.app import app
# Votre code de test ici
"
```

### 3. Base clean
```bash
# Réinitialiser base SQLite
rm -f test_scorpius.db
python -c "
import asyncio
import os
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_scorpius.db'
from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init_db())
"
```

---

## 🚀 Workflow de Test Recommandé

### Test rapide (2 minutes)
```bash
# 1. Démarrage SQLite
uvicorn main:app --reload --env-file .env.local

# 2. Test santé
curl http://localhost:8000/health

# 3. Interface web
open http://localhost:8000/docs
```

### Test complet (10 minutes)
```bash
# 1. Tests automatisés
pytest tests/unit -v

# 2. API manuelle
# - Enregistrement
# - Connexion
# - Upload document
# - Profil entreprise
# - Analyse

# 3. Interface Swagger
# Tester tous endpoints via http://localhost:8000/docs
```

### Test proche production (20 minutes)
```bash
# 1. Docker complet
docker-compose -f docker-compose.dev.yml up -d

# 2. Tests avec PostgreSQL
# Tous les tests ci-dessus

# 3. Performance
# Tests de charge basiques
```

---

## ✅ Checklist Tests Locaux

- [ ] API démarre sans erreur
- [ ] Base de données connectée
- [ ] Enregistrement utilisateur fonctionne
- [ ] Connexion et JWT valides
- [ ] Upload de documents opérationnel
- [ ] Traitement PDF fonctionnel
- [ ] Profil entreprise créable
- [ ] Analyse de correspondance active
- [ ] Interface Swagger accessible
- [ ] Tests automatisés passent

**🎉 Si tous les points sont validés, Scorpius est prêt pour la production !**