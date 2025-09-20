# Scorpius Project - MVP Bid Manager Intelligent Copilot

> **Copilote intelligent pour bid manager d'ESN française spécialisé dans les appels d'offres publics**

## 🎯 Objectif

Backend d'une application qui assiste les bid managers dans la réponse aux appels d'offres publics français, couvrant tout le cycle : lecture, compréhension, adaptation, génération, conformité, et stratégie.

## 🏗️ Architecture

- **Stack**: Python 3.11+, FastAPI 0.109+, PostgreSQL 15+, Redis
- **Architecture**: Hexagonale avec Domain-Driven Design
- **Évolutivité**: Plugin architecture pour extensibilité future
- **Tests**: TDD avec 100% de couverture des contrats d'API

## 📊 Fonctionnalités MVP

### 🔐 Authentification & Gestion Utilisateurs
- Inscription/connexion avec JWT + refresh tokens
- Gestion des profils d'entreprise avec capacités et certifications
- Système de rôles (bid_manager, admin)

### 📄 Gestion Documentaire
- Upload et validation des documents PDF
- Extraction automatique des exigences techniques et fonctionnelles
- Indexation et recherche full-text
- Versioning et audit trail

### 🎯 Analyse & Matching
- Analyse automatique des capacités vs exigences
- Scoring de compatibilité
- Recommandations d'amélioration
- Détection des gaps techniques

### 📝 Génération de Réponses
- Templates de réponses personnalisables
- Génération assistée de contenu
- Vérification de conformité automatique
- Export multi-formats (PDF, Word)

## 🚀 État d'Avancement

### ✅ Phases Complétées (42/104 tâches - 40.4%)

**Phase 3.1: Setup & Configuration** ✅
- Structure projet, Docker, configuration Python

**Phase 3.2: Database & Models** ✅
- 10 modèles SQLAlchemy avec Alembic
- Architecture multi-tenant ready

**Phase 3.3: Tests First (TDD)** ✅
- 16 tests de contrats d'API
- 4 tests d'intégration end-to-end
- 20 fichiers de tests couvrant 100% des fonctionnalités

### 🔄 Prochaines Phases

**Phase 3.4: Repository Layer** (En cours)
- Pattern Repository pour abstraction données
- CRUD operations avec pagination

**Phase 3.5: Core Services**
- Services métier (auth, documents, analysis)
- Pipeline de traitement documentaire

**Phase 3.6: API Implementation**
- 15+ endpoints RESTful
- Validation OpenAPI 3.0

## 🛠️ Installation & Développement

### Prérequis
```bash
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optionnel)
```

### Setup Local
```bash
# Clone du repository
git clone https://github.com/[username]/scorpiusProject.git
cd scorpiusProject

# Installation des dépendances
pip install -r requirements-dev.txt

# Configuration environnement
cp .env.example .env
# Éditer .env avec vos paramètres

# Setup base de données
scripts/init-db.sql
alembic upgrade head

# Lancement des tests (TDD - doivent échouer pour l'instant)
pytest tests/contract/ -v
pytest tests/integration/ -v
```

### Développement avec Docker
```bash
docker-compose up -d
```

## 📚 Documentation

- **Architecture**: [`specs/001-construire-le-mvp/plan.md`](specs/001-construire-le-mvp/plan.md)
- **Modèle de données**: [`specs/001-construire-le-mvp/data-model.md`](specs/001-construire-le-mvp/data-model.md)
- **API Contracts**: [`specs/001-construire-le-mvp/contracts/openapi.yaml`](specs/001-construire-le-mvp/contracts/openapi.yaml)
- **Tâches**: [`specs/001-construire-le-mvp/tasks.md`](specs/001-construire-le-mvp/tasks.md)
- **Constitution**: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)

## 🧪 Tests

### Stratégie TDD
- **Tests de contrats**: Validation OpenAPI et comportements d'API
- **Tests d'intégration**: Workflows utilisateur complets
- **Tests unitaires**: Isolation des services (à venir)

### Lancement
```bash
# Tests de contrats (doivent échouer avant implémentation)
pytest tests/contract/ -v

# Tests d'intégration
pytest tests/integration/ -v

# Coverage
pytest --cov=src tests/
```

## 🔮 Roadmap & Evolution

### Features Déferrées (Post-MVP)
- **NLP Avancé**: LLM pour analyse sémantique des documents
- **Multi-tenancy**: Isolation complète par organisation
- **Workflows Collaboratifs**: Édition collaborative des réponses
- **Analytics**: Tableaux de bord et métriques de performance
- **Intégrations**: APIs gouvernementales, outils métier

### Architecture Évolutive
- Plugin system pour processeurs de documents
- Event sourcing pour audit complet
- API versioning pour breaking changes
- Microservices ready

## 🏛️ Conformité & Sécurité

- **RGPD**: Protection des données personnelles
- **ISO 27001**: Sécurité de l'information
- **Accessibilité**: RGAA standards
- **Audit**: Traçabilité complète des actions

## 🤝 Contribution

Ce projet suit une approche TDD stricte :
1. **Tests d'abord**: Tous les tests doivent être écrits avant l'implémentation
2. **Red-Green-Refactor**: Tests échouent → Implémentation → Refactoring
3. **Couverture**: 80%+ sur les services métier

## 📄 Licence

[À définir selon les besoins du projet]

---

**Développé avec ❤️ pour optimiser les réponses aux appels d'offres publics français**