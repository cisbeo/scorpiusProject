#!/bin/bash

# Script de configuration environnement de développement - Scorpius Project
# Usage: ./scripts/dev-setup.sh [local|docker]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Configuration environnement local (SQLite)
setup_local() {
    log "🚀 Configuration environnement local (SQLite)..."

    # Vérifier Python
    if ! command -v python3 &> /dev/null; then
        error "Python 3.11+ requis"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    info "Python version détectée: $PYTHON_VERSION"

    # Créer environnement virtuel
    if [[ ! -d "venv" ]]; then
        log "Création environnement virtuel Python..."
        python3 -m venv venv
    fi

    source venv/bin/activate

    # Mise à jour pip
    log "Mise à jour pip..."
    pip install --upgrade pip

    # Installation des dépendances
    log "Installation des dépendances de développement..."
    pip install -r requirements.txt
    pip install -r requirements-dev.txt

    # SQLite async pour développement local
    pip install aiosqlite

    # Créer dossiers nécessaires
    log "Création des dossiers de développement..."
    mkdir -p uploads temp logs .coverage_reports

    # Vérifier fichier de configuration
    if [[ ! -f ".env.local" ]]; then
        log "Création fichier .env.local..."
        cp .env.example .env.local
        warning "Modifiez .env.local si nécessaire"
    fi

    # Initialiser base de données SQLite
    log "Initialisation base de données SQLite..."
    python3 -c "
import asyncio
import os
import sys
sys.path.append('.')

os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_scorpius.db'

from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Base de données SQLite initialisée')
    except Exception as e:
        print(f'❌ Erreur initialisation DB: {e}')
        exit(1)

asyncio.run(init_db())
"

    # Installer pre-commit hooks
    log "Installation pre-commit hooks..."
    pre-commit install

    # Vérifier installation
    log "Vérification de l'installation..."
    python3 -c "
import sys
print(f'✅ Python: {sys.version}')
"

    pip list | grep -E "(fastapi|sqlalchemy|pytest)" || true

    log "✅ Environnement local configuré avec succès !"
    info "Démarrage: source venv/bin/activate && ./scripts/dev-start.sh local"
}

# Configuration environnement Docker
setup_docker() {
    log "🐳 Configuration environnement Docker..."

    # Vérifier Docker
    if ! command -v docker &> /dev/null; then
        error "Docker n'est pas installé"
        info "Installation: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose n'est pas installé"
        exit 1
    fi

    # Vérifier que Docker fonctionne
    if ! docker info &> /dev/null; then
        error "Docker n'est pas démarré"
        exit 1
    fi

    log "Docker version: $(docker --version)"
    log "Docker Compose version: $(docker-compose --version)"

    # Créer fichier environnement Docker
    if [[ ! -f ".env.docker" ]]; then
        log "Création fichier .env.docker..."
        info "Fichier .env.docker créé avec configuration par défaut"
    fi

    # Créer dossiers pour volumes
    log "Création des dossiers pour volumes Docker..."
    mkdir -p uploads temp logs nginx/ssl

    # Build des images
    log "Construction des images Docker..."
    docker-compose build

    # Démarrer les services
    log "Démarrage des services Docker..."
    docker-compose up -d db redis

    # Attendre que PostgreSQL soit prêt
    log "Attente démarrage PostgreSQL..."
    for i in {1..30}; do
        if docker-compose exec -T db pg_isready -U scorpius -d scorpius_mvp &> /dev/null; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            error "PostgreSQL n'a pas démarré"
            exit 1
        fi
        sleep 2
    done

    log "✅ Services Docker démarrés"

    # Initialiser base de données
    log "Initialisation base de données PostgreSQL..."
    docker-compose run --rm app python -c "
import asyncio
from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Base de données PostgreSQL initialisée')
    except Exception as e:
        print(f'❌ Erreur initialisation DB: {e}')
        exit(1)

asyncio.run(init_db())
"

    log "✅ Environnement Docker configuré avec succès !"
    info "Démarrage: ./scripts/dev-start.sh docker"
    info "pgAdmin: http://localhost:5050 (admin@scorpiusproject.fr / admin)"
}

# Installation outils de développement
install_dev_tools() {
    log "🔧 Installation outils de développement..."

    # Outils globaux utiles
    pip install --user --upgrade \
        httpie \
        uvicorn[standard] \
        pytest-xdist

    # Outils système (optionnel)
    if command -v brew &> /dev/null; then
        info "Installation via Homebrew..."
        brew install jq curl wget git
    elif command -v apt &> /dev/null; then
        info "Installation via apt..."
        sudo apt update
        sudo apt install -y jq curl wget git build-essential
    fi

    log "✅ Outils de développement installés"
}

# Tests de validation
validate_setup() {
    log "🧪 Validation de l'installation..."

    case "$1" in
        local)
            if [[ ! -f "test_scorpius.db" ]]; then
                error "Base de données SQLite non trouvée"
                exit 1
            fi

            source venv/bin/activate
            python3 -c "
import sys
sys.path.append('.')
from src.db.session import async_engine
print('✅ Connexion SQLite OK')
"
            ;;

        docker)
            if ! docker-compose ps | grep -q "Up"; then
                error "Services Docker non démarrés"
                exit 1
            fi

            docker-compose exec -T db pg_isready -U scorpius -d scorpius_mvp
            docker-compose exec -T redis redis-cli ping
            ;;
    esac

    log "✅ Validation réussie"
}

# Affichage aide
show_help() {
    echo "Script de configuration environnement de développement - Scorpius Project"
    echo
    echo "Usage: $0 [ENVIRONMENT] [OPTIONS]"
    echo
    echo "ENVIRONMENTS:"
    echo "  local    - Configuration locale avec SQLite (rapide)"
    echo "  docker   - Configuration Docker avec PostgreSQL/Redis (complet)"
    echo
    echo "OPTIONS:"
    echo "  --tools  - Installer outils de développement"
    echo "  --check  - Valider l'installation existante"
    echo
    echo "EXEMPLES:"
    echo "  $0 local                 # Setup rapide local"
    echo "  $0 docker                # Setup complet Docker"
    echo "  $0 local --tools         # Setup local + outils"
    echo "  $0 --check local         # Valider setup local"
    echo
    echo "WORKFLOW RECOMMANDÉ:"
    echo "  1. $0 local              # Premier setup"
    echo "  2. ./scripts/dev-start.sh local   # Démarrage"
    echo "  3. ./scripts/dev-test.sh          # Tests"
}

# Main script logic
ENVIRONMENT=""
INSTALL_TOOLS=false
CHECK_ONLY=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        local|docker)
            ENVIRONMENT=$arg
            ;;
        --tools)
            INSTALL_TOOLS=true
            ;;
        --check)
            CHECK_ONLY=true
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            warning "Argument inconnu: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Vérifier environnement spécifié
if [[ -z "$ENVIRONMENT" && "$CHECK_ONLY" == false ]]; then
    error "Environnement requis: local ou docker"
    show_help
    exit 1
fi

# Exécuter actions
if [[ "$CHECK_ONLY" == true ]]; then
    validate_setup "$ENVIRONMENT"
elif [[ "$INSTALL_TOOLS" == true ]]; then
    install_dev_tools
    if [[ -n "$ENVIRONMENT" ]]; then
        setup_$ENVIRONMENT
        validate_setup "$ENVIRONMENT"
    fi
else
    setup_$ENVIRONMENT
    validate_setup "$ENVIRONMENT"
fi

echo
log "🎉 Configuration terminée avec succès !"
info "Prochaines étapes:"
info "  - Démarrage: ./scripts/dev-start.sh $ENVIRONMENT"
info "  - Tests: ./scripts/dev-test.sh"
info "  - Documentation: http://localhost:8000/docs"