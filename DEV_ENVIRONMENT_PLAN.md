# 🛠️ Plan d'Environnement de Développement - Scorpius Project

## 🎯 Objectif
Configurer un environnement de développement complet permettant d'implémenter efficacement les nouvelles fonctionnalités et de réaliser des tests d'intégration robustes.

## 📋 Analyse de l'existant

### ✅ Ce qui est déjà configuré
- Docker Compose local avec PostgreSQL + Redis + pgAdmin
- Configuration SQLite pour tests rapides
- Scripts de test automatisés (`test_local.sh`)
- Environnement de variables (.env.local)
- Tests d'intégration de base
- Outils de qualité de code (ruff, mypy, bandit)

### 🔴 Points à améliorer
- Pas de hot-reload pour le développement
- Tests d'intégration incomplets
- Environnement de debug limité
- Pas de mock des services externes
- Documentation dev incomplète

## 🏗️ Architecture de développement recommandée

### Option 1: Développement local avec SQLite (rapide)
```
Local Machine
├── FastAPI (uvicorn --reload)
├── SQLite (test_scorpius.db)
├── Uploads locaux (./uploads)
└── Logs locaux (./logs)
```

### Option 2: Développement avec Docker (plus proche de prod)
```
Docker Compose
├── API Container (volume mounted)
├── PostgreSQL Container
├── Redis Container
├── pgAdmin Container
└── Shared volumes
```

## 🔧 Configuration recommandée

### 1. Setup de base pour développement

#### Structure des environnements
```bash
# Environnements multiples
.env.local          # SQLite + développement rapide
.env.docker         # Docker Compose local
.env.test           # Tests automatisés
.env.staging        # Pré-production
.env.prod           # Production
```

#### Scripts de développement
```bash
# Scripts utilitaires
scripts/
├── dev-setup.sh         # Installation environnement
├── dev-start.sh         # Démarrage mode dev
├── dev-test.sh          # Tests complets
├── dev-reset.sh         # Reset environnement
└── dev-lint.sh          # Qualité code
```

### 2. Configuration IDE et outils

#### VSCode (recommandé)
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        ".pytest_cache": true,
        ".ruff_cache": true,
        ".mypy_cache": true
    }
}
```

#### Extensions VSCode recommandées
- Python
- Pylance
- Ruff
- Docker
- REST Client
- GitLens
- Thunder Client (tests API)

### 3. Hot-reload et développement continu

#### Configuration uvicorn pour développement
```python
# dev_server.py
import uvicorn
from pathlib import Path

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"],  # Surveiller seulement src/
        log_level="debug",
        access_log=True,
        env_file=".env.local"
    )
```

#### Watch files pour auto-restart
```bash
# Avec watchdog pour surveillance fichiers
pip install watchdog[watchmedo]

# Auto-restart sur changement
watchmedo auto-restart --pattern="*.py" --recursive -- python dev_server.py
```

## 🧪 Configuration des tests

### 1. Tests d'intégration étendus

#### Structure des tests
```
tests/
├── unit/                    # Tests unitaires
│   ├── test_auth.py
│   ├── test_documents.py
│   └── test_company.py
├── integration/             # Tests d'intégration API
│   ├── test_auth_flow.py
│   ├── test_document_upload.py
│   ├── test_company_crud.py
│   └── test_capabilities.py
├── e2e/                     # Tests end-to-end
│   ├── test_complete_workflow.py
│   └── test_user_journey.py
├── fixtures/                # Données de test
│   ├── test_documents/
│   └── test_data.py
└── conftest.py             # Configuration pytest
```

#### Configuration pytest avancée
```python
# conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from src.db.base import Base
from src.db.session import get_async_db

# Base de données test en mémoire
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_db():
    """Create test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()

@pytest.fixture
async def client(async_db):
    """Create test client with database override."""
    app.dependency_overrides[get_async_db] = lambda: async_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
def test_user_data():
    """Sample user data for tests."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "role": "bid_manager"
    }

@pytest.fixture
async def authenticated_user(client, test_user_data):
    """Create and authenticate a test user."""
    # Register user
    await client.post("/api/v1/auth/register", json=test_user_data)

    # Login
    response = await client.post("/api/v1/auth/login", json={
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    })

    token = response.json()["data"]["access_token"]
    return {"token": token, "user_data": test_user_data}
```

### 2. Tests de performance et charge

#### Configuration des tests de performance
```python
# tests/performance/test_load.py
import pytest
import asyncio
from httpx import AsyncClient
import time

@pytest.mark.performance
async def test_concurrent_users():
    """Test with multiple concurrent users."""
    async def make_request():
        async with AsyncClient(base_url="http://localhost:8000") as client:
            response = await client.get("/health")
            return response.status_code == 200

    # Simuler 50 utilisateurs concurrents
    tasks = [make_request() for _ in range(50)]
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    duration = time.time() - start_time

    assert all(results), "Certaines requêtes ont échoué"
    assert duration < 5.0, f"Temps de réponse trop long: {duration}s"

@pytest.mark.performance
async def test_document_upload_performance():
    """Test upload performance with large files."""
    # Test avec fichiers de différentes tailles
    pass
```

### 3. Mock et simulation

#### Mock des services externes
```python
# tests/mocks/external_services.py
from unittest.mock import AsyncMock, patch
import pytest

@pytest.fixture
def mock_email_service():
    """Mock email service."""
    with patch('src.services.email_service.EmailService') as mock:
        mock.send_email = AsyncMock(return_value=True)
        yield mock

@pytest.fixture
def mock_document_processor():
    """Mock document processing."""
    with patch('src.processors.pdf_processor.PDFProcessor') as mock:
        mock.extract_text = AsyncMock(return_value="Mocked text content")
        mock.extract_metadata = AsyncMock(return_value={"pages": 5})
        yield mock
```

## 🔍 Debugging et monitoring

### 1. Configuration logging développement

#### Logging structuré pour debug
```python
# src/core/logging.py
import logging
import sys
from datetime import datetime
from typing import Dict, Any

class DevFormatter(logging.Formatter):
    """Formatter spécialisé pour développement."""

    def format(self, record):
        # Couleurs pour terminal
        colors = {
            'DEBUG': '\033[36m',     # Cyan
            'INFO': '\033[32m',      # Vert
            'WARNING': '\033[33m',   # Jaune
            'ERROR': '\033[31m',     # Rouge
            'CRITICAL': '\033[35m',  # Magenta
        }

        color = colors.get(record.levelname, '')
        reset = '\033[0m'

        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]

        return f"{color}[{timestamp}] {record.levelname:8} | {record.name:20} | {record.getMessage()}{reset}"

def setup_dev_logging():
    """Configuration logging pour développement."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Handler console avec couleurs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(DevFormatter())
    console_handler.setLevel(logging.DEBUG)

    # Handler fichier pour debug
    file_handler = logging.FileHandler('logs/dev_debug.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
    ))
    file_handler.setLevel(logging.DEBUG)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Réduire verbosité des libraries externes
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

### 2. Profiling et performance

#### Profiling automatique
```python
# src/middleware/profiling.py
import cProfile
import pstats
import io
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class ProfilingMiddleware(BaseHTTPMiddleware):
    """Middleware de profiling pour développement."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/profile/"):
            # Profiling activé pour ces endpoints
            profiler = cProfile.Profile()
            profiler.enable()

            response = await call_next(request)

            profiler.disable()

            # Sauvegarder stats
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
            ps.print_stats()

            # Ajouter dans headers pour debug
            response.headers["X-Profile-Stats"] = s.getvalue()[:1000]

            return response
        else:
            return await call_next(request)
```

## 🚀 Workflow de développement

### 1. Démarrage rapide quotidien

#### Script dev-start.sh
```bash
#!/bin/bash
# scripts/dev-start.sh

set -e

echo "🚀 Démarrage environnement Scorpius Dev"

# Activer environnement virtuel
if [[ ! -d "venv" ]]; then
    echo "Création environnement virtuel..."
    python3 -m venv venv
fi

source venv/bin/activate

# Installer/mettre à jour dépendances
echo "📦 Mise à jour dépendances..."
pip install -r requirements.txt -r requirements-dev.txt

# Créer dossiers nécessaires
mkdir -p uploads temp logs

# Vérifier base de données
if [[ ! -f "test_scorpius.db" ]]; then
    echo "🗄️ Initialisation base de données..."
    python scripts/init_local_db.py
fi

# Démarrer serveur de développement
echo "🌟 Démarrage serveur..."
echo "API: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo "Health: http://localhost:8000/health"
echo ""

python dev_server.py
```

### 2. Tests automatisés continus

#### Configuration GitHub Actions pour dev
```yaml
# .github/workflows/dev-tests.yml
name: Dev Tests

on:
  push:
    branches: [ develop, feature/* ]
  pull_request:
    branches: [ develop, main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run linting
      run: |
        ruff check src tests
        mypy src

    - name: Run tests
      run: |
        pytest tests/ -v --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### 3. Pre-commit hooks avancés

#### Configuration .pre-commit-config.yaml étendue
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: check-docstring-first
      - id: debug-statements

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [ --fix, --exit-non-zero-on-fix ]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-r', 'src/']

  - repo: local
    hooks:
      - id: pytest-fast
        name: Fast tests
        entry: pytest tests/unit -x
        language: system
        pass_filenames: false
        always_run: true
```

## 📊 Métriques et monitoring dev

### 1. Dashboard développement

#### Endpoint de métriques dev
```python
# src/api/dev/metrics.py
from fastapi import APIRouter, Depends
from src.core.auth import get_current_user
import psutil
import time

router = APIRouter(prefix="/dev", tags=["development"])

@router.get("/metrics")
async def get_dev_metrics():
    """Métriques pour développement uniquement."""
    return {
        "server": {
            "uptime": time.time() - start_time,
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        },
        "database": {
            "connections": await get_db_connection_count(),
            "queries_count": await get_queries_count()
        },
        "api": {
            "endpoints_hit": endpoint_stats,
            "average_response_time": response_times.average()
        }
    }

@router.get("/logs/tail")
async def tail_logs(lines: int = 50):
    """Dernières lignes de logs."""
    with open('logs/dev_debug.log', 'r') as f:
        return {"logs": f.readlines()[-lines:]}
```

## 🎯 Objectifs et KPIs

### Objectifs de l'environnement de développement
1. **Temps de setup** < 5 minutes pour nouvel développeur
2. **Hot-reload** < 2 secondes après modification
3. **Tests complets** < 30 secondes
4. **Coverage** > 80% pour toutes les fonctionnalités
5. **Feedback temps réel** sur qualité code

### Métriques de succès
- ✅ Tests d'intégration passent à 100%
- ✅ Nouveaux endpoints testés automatiquement
- ✅ Debug facile avec logs structurés
- ✅ Performance monitorée en continu
- ✅ Documentation à jour automatiquement

## 📚 Documentation et resources

### Documentation automatique
- OpenAPI/Swagger toujours à jour
- Docstrings complètes avec exemples
- Tests comme documentation vivante
- Architecture Decision Records (ADR)

### Resources utiles
- [FastAPI Best Practices](https://fastapi-best-practices.netlify.app/)
- [AsyncIO Testing](https://docs.python.org/3/library/asyncio-dev.html)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)

---

**✅ Plan d'environnement de développement prêt pour implémentation**

Ce plan couvre tous les aspects pour un développement efficace et des tests d'intégration robustes.