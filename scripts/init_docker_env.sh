#!/bin/bash

# Script d'initialisation robuste pour l'environnement Docker
# Scorpius Project - Résout tous les problèmes d'initialisation
# Usage: ./scripts/init_docker_env.sh [--clean] [--verbose] [--port PORT]
#
# Corrections appliquées (2025-09-25):
# - Export automatique DATABASE_URL pour éviter SQLite
# - Port par défaut changé à 5434 (évite conflits)
# - Initialisation complète avec tous les modèles
# - Instructions claires pour l'API avec DATABASE_URL

set -e

# Configuration
DEFAULT_PG_PORT=5434  # Éviter 5432 (système) et 5433 (souvent utilisé)
POSTGRES_USER="scorpius"
POSTGRES_PASSWORD="scorpiusdev"
POSTGRES_DB="scorpius_dev"
REDIS_PORT=6379

# Variables globales
VERBOSE=false
CLEAN=false
START_API=false
INTERACTIVE=true
PG_PORT=$DEFAULT_PG_PORT
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions de logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✅]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1"
}

log_error() {
    echo -e "${RED}[❌]${NC} $1"
}

log_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Fonction d'aide
show_help() {
    echo "Script d'initialisation Docker pour Scorpius Project"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --clean         Nettoie complètement l'environnement avant de démarrer"
    echo "  --verbose       Affiche les logs détaillés"
    echo "  --port PORT     Port PostgreSQL à utiliser (défaut: $DEFAULT_PG_PORT)"
    echo "  --start-api     Démarre automatiquement l'API après l'initialisation"
    echo "  --no-interactive  Désactive les prompts interactifs"
    echo "  --help          Affiche cette aide"
    echo ""
    echo "EXEMPLES:"
    echo "  $0                    # Installation standard"
    echo "  $0 --clean            # Réinitialisation complète"
    echo "  $0 --clean --start-api # Réinit et démarre l'API"
    echo "  $0 --port 5434        # Utilise un port spécifique"
    echo "  $0 --clean --verbose  # Réinit avec logs détaillés"
}

# Parse des arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --port)
            PG_PORT="$2"
            shift 2
            ;;
        --start-api)
            START_API=true
            shift
            ;;
        --no-interactive)
            INTERACTIVE=false
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Option inconnue: $1"
            show_help
            exit 1
            ;;
    esac
done

# Vérification des prérequis
check_prerequisites() {
    log_info "Vérification des prérequis..."

    # Vérifier Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker n'est pas installé"
        echo "Installation: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Vérifier Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose n'est pas installé"
        exit 1
    fi

    # Vérifier que Docker est démarré
    if ! docker info &> /dev/null; then
        log_error "Docker n'est pas démarré"
        exit 1
    fi

    # Vérifier Python 3.11+
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 n'est pas installé"
        exit 1
    fi

    log_success "Prérequis vérifiés"
}

# Détection de port disponible
detect_available_port() {
    local port=$1

    # Vérifier si le port est utilisé
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        log_warning "Port $port déjà utilisé"

        # Chercher un port alternatif (évite 5432 pour PostgreSQL système)
        for alt_port in 5434 5435 5436 5437 5438; do
            if ! lsof -Pi :$alt_port -sTCP:LISTEN -t >/dev/null 2>&1; then
                log_info "Port alternatif trouvé: $alt_port"
                PG_PORT=$alt_port
                return 0
            fi
        done

        log_error "Aucun port PostgreSQL disponible (5434-5438)"
        exit 1
    else
        log_debug "Port $port disponible"
        return 0
    fi
}

# Nettoyage de l'environnement
cleanup_environment() {
    log_info "Nettoyage de l'environnement existant..."

    cd "$PROJECT_ROOT"

    # Arrêter et supprimer les conteneurs existants
    if docker ps -a | grep -E "(scorpius-postgres|scorpius-redis)" &> /dev/null; then
        log_debug "Arrêt des conteneurs existants..."
        docker stop scorpius-postgres-local scorpius-redis-local 2>/dev/null || true
        docker rm scorpius-postgres-local scorpius-redis-local 2>/dev/null || true
    fi

    # Nettoyer avec docker-compose si le fichier existe
    if [ -f "docker-compose.local.yml" ]; then
        log_debug "Nettoyage via docker-compose..."
        docker-compose -f docker-compose.local.yml down 2>/dev/null || true

        if [ "$CLEAN" = true ]; then
            docker-compose -f docker-compose.local.yml down -v 2>/dev/null || true
            log_success "Volumes Docker supprimés"
        fi
    fi

    # Supprimer les anciennes bases SQLite
    if [ "$CLEAN" = true ]; then
        rm -f test_scorpius.db scorpius.db 2>/dev/null || true
        log_debug "Bases SQLite supprimées"
    fi

    log_success "Environnement nettoyé"
}

# Création du docker-compose.local.yml
create_docker_compose() {
    log_info "Création du fichier docker-compose.local.yml..."

    cat > "$PROJECT_ROOT/docker-compose.local.yml" <<EOF
services:
  postgres:
    image: postgres:15-alpine
    container_name: scorpius-postgres-local
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "${PG_PORT}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - scorpius-network

  redis:
    image: redis:7-alpine
    container_name: scorpius-redis-local
    ports:
      - "${REDIS_PORT}:6379"
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep PONG"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - scorpius-network

volumes:
  postgres_data:

networks:
  scorpius-network:
    driver: bridge
EOF

    log_success "docker-compose.local.yml créé avec port PostgreSQL: $PG_PORT"
}

# Mise à jour du fichier .env
update_env_file() {
    log_info "Mise à jour du fichier .env..."

    ENV_FILE="$PROJECT_ROOT/.env"

    # Sauvegarder l'ancien .env si nécessaire
    if [ -f "$ENV_FILE" ] && [ "$CLEAN" = true ]; then
        cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        log_debug "Sauvegarde créée: ${ENV_FILE}.backup.*"
    fi

    # Si le fichier n'existe pas, le créer depuis l'exemple
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
        else
            # Créer un .env minimal
            cat > "$ENV_FILE" <<EOF
# Configuration Scorpius Project - Généré automatiquement

# Application Settings
APP_NAME=ScorpiusProject
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# API Configuration
API_VERSION=v1
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database Configuration
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PG_PORT}/${POSTGRES_DB}
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30

# Redis Configuration
REDIS_URL=redis://localhost:${REDIS_PORT}/0
REDIS_MAX_CONNECTIONS=50
REDIS_DECODE_RESPONSES=true

# Security
SECRET_KEY=your-secret-key-here-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]

# File Upload
UPLOAD_MAX_SIZE_MB=10
UPLOAD_ALLOWED_EXTENSIONS=[".pdf",".docx",".doc",".txt"]
UPLOAD_DIR=uploads

# Mistral AI Configuration (si disponible)
# MISTRAL_API_KEY=your-mistral-api-key
# MISTRAL_MODEL=mistral-large-latest
EOF
        fi
    fi

    # Mettre à jour DATABASE_URL avec le bon port
    DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PG_PORT}/${POSTGRES_DB}"

    # Utiliser sed pour mettre à jour DATABASE_URL
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" "$ENV_FILE"
    else
        # Linux
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" "$ENV_FILE"
    fi

    log_success ".env mis à jour avec DATABASE_URL: $DATABASE_URL"
}

# Démarrage des services Docker
start_docker_services() {
    log_info "Démarrage des services Docker..."

    cd "$PROJECT_ROOT"

    # Démarrer les services
    docker-compose -f docker-compose.local.yml up -d

    # Attendre que PostgreSQL soit prêt
    log_info "Attente du démarrage de PostgreSQL..."
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if docker exec scorpius-postgres-local pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB} &> /dev/null; then
            log_success "PostgreSQL est prêt"
            break
        fi

        attempt=$((attempt + 1))
        log_debug "Tentative $attempt/$max_attempts..."
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        log_error "PostgreSQL n'a pas démarré après $max_attempts tentatives"
        docker-compose -f docker-compose.local.yml logs postgres
        exit 1
    fi

    # Vérifier Redis
    if docker exec scorpius-redis-local redis-cli ping &> /dev/null; then
        log_success "Redis est prêt"
    else
        log_error "Redis n'a pas démarré"
        exit 1
    fi
}

# Création de l'environnement virtuel Python
setup_python_venv() {
    log_info "Configuration de l'environnement Python..."

    cd "$PROJECT_ROOT"

    # Chercher Python 3.11
    PYTHON_CMD=""
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3 &> /dev/null; then
        # Vérifier la version
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ "$PYTHON_VERSION" == "3.11" ]] || [[ "$PYTHON_VERSION" == "3.12" ]]; then
            PYTHON_CMD="python3"
        fi
    fi

    if [ -z "$PYTHON_CMD" ]; then
        log_error "Python 3.11+ non trouvé"
        exit 1
    fi

    log_debug "Utilisation de $PYTHON_CMD"

    # Créer venv si nécessaire
    if [ ! -d "venv_py311" ]; then
        log_info "Création de l'environnement virtuel..."
        $PYTHON_CMD -m venv venv_py311
    fi

    # Activer et installer les dépendances
    source venv_py311/bin/activate

    log_info "Installation des dépendances Python..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    pip install --quiet asyncpg  # S'assurer qu'asyncpg est installé

    log_success "Environnement Python configuré"
}

# Initialisation de la base de données
initialize_database() {
    log_info "Initialisation de la base de données PostgreSQL..."

    cd "$PROJECT_ROOT"
    source venv_py311/bin/activate

    # Créer le script d'initialisation Python
    python3 "$SCRIPT_DIR/init_postgres_all_models.py"

    if [ $? -eq 0 ]; then
        log_success "Base de données initialisée avec succès"
    else
        log_error "Erreur lors de l'initialisation de la base de données"
        exit 1
    fi
}

# Vérification finale
verify_installation() {
    log_info "Vérification de l'installation..."

    # Vérifier les conteneurs
    if ! docker ps | grep -q scorpius-postgres-local; then
        log_error "PostgreSQL n'est pas en cours d'exécution"
        exit 1
    fi

    if ! docker ps | grep -q scorpius-redis-local; then
        log_error "Redis n'est pas en cours d'exécution"
        exit 1
    fi

    # Vérifier la connexion à la base de données
    export PGPASSWORD=${POSTGRES_PASSWORD}
    if psql -h localhost -p ${PG_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT 1;" &> /dev/null; then
        log_success "Connexion PostgreSQL OK"
    else
        log_warning "psql non disponible localement, test via Docker..."
        if docker exec scorpius-postgres-local psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT 1;" &> /dev/null; then
            log_success "Connexion PostgreSQL OK (via Docker)"
        else
            log_error "Impossible de se connecter à PostgreSQL"
            exit 1
        fi
    fi

    # Compter les tables
    TABLE_COUNT=$(docker exec scorpius-postgres-local psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')

    log_success "Installation vérifiée: $TABLE_COUNT tables créées"
}

# Fonction pour démarrer l'API
start_api_server() {
    log_info "Démarrage de l'API Scorpius..."

    # Vérifier si le script start_api.sh existe
    if [ -f "$SCRIPT_DIR/start_api.sh" ]; then
        # Utiliser le script start_api.sh
        exec "$SCRIPT_DIR/start_api.sh"
    else
        # Démarrage manuel
        export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PG_PORT}/${POSTGRES_DB}"
        log_info "DATABASE_URL exporté: $DATABASE_URL"

        cd "$PROJECT_ROOT"
        source venv_py311/bin/activate

        echo ""
        echo -e "${GREEN}🚀 API Scorpius démarrée${NC}"
        echo -e "${BLUE}📚 Documentation:${NC} http://localhost:8000/docs"
        echo -e "${BLUE}📊 API:${NC} http://localhost:8000/api/v1"
        echo ""
        echo "Appuyez sur Ctrl+C pour arrêter l'API"
        echo "============================================================"

        uvicorn src.api.v1.app:app --reload --port 8000 --host 0.0.0.0
    fi
}

# Programme principal
main() {
    echo "🚀 Initialisation de l'environnement Docker Scorpius"
    echo "=================================================="
    echo ""

    # Vérifications
    check_prerequisites

    # Détection du port disponible
    detect_available_port $PG_PORT

    # Nettoyage si demandé
    if [ "$CLEAN" = true ]; then
        cleanup_environment
    fi

    # Configuration
    create_docker_compose
    update_env_file

    # Démarrage
    start_docker_services
    setup_python_venv

    # Initialisation DB
    initialize_database

    # Export DATABASE_URL pour éviter que l'API utilise SQLite
    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PG_PORT}/${POSTGRES_DB}"
    log_info "DATABASE_URL exporté: $DATABASE_URL"

    # Créer un fichier d'export pour faciliter l'utilisation
    echo "export DATABASE_URL='$DATABASE_URL'" > "$PROJECT_ROOT/.env.export"
    log_info "Fichier .env.export créé pour faciliter l'export"

    # Vérification
    verify_installation

    # Proposer de démarrer l'API
    if [ "$START_API" = true ]; then
        log_info "Démarrage automatique de l'API..."
        start_api_server
    elif [ "$INTERACTIVE" = true ]; then
        echo ""
        echo -e "${GREEN}✨ L'environnement Docker est prêt !${NC}"
        echo ""
        read -p "Voulez-vous démarrer l'API maintenant ? (O/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Oo]$ ]] || [[ -z $REPLY ]]; then
            start_api_server
        fi
    fi

    echo ""
    echo "✨ Installation terminée avec succès!"
    echo ""
    echo "📝 Configuration:"
    echo "   - PostgreSQL: localhost:${PG_PORT}"
    echo "   - Redis: localhost:${REDIS_PORT}"
    echo "   - Database: ${POSTGRES_DB}"
    echo "   - User: ${POSTGRES_USER}"
    echo ""
    echo "🔧 Commandes utiles:"
    echo "   - Démarrer l'API avec PostgreSQL:"
    echo "     export DATABASE_URL=\"postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${PG_PORT}/${POSTGRES_DB}\""
    echo "     source venv_py311/bin/activate && uvicorn src.api.v1.app:app --reload --port 8000"
    echo ""
    echo "   - OU utiliser le fichier d'export:"
    echo "     source .env.export"
    echo "     source venv_py311/bin/activate && uvicorn src.api.v1.app:app --reload --port 8000"
    echo ""
    echo "   - Voir les logs: docker-compose -f docker-compose.local.yml logs -f"
    echo "   - Arrêter: docker-compose -f docker-compose.local.yml down"
    echo "   - Vérifier: ./scripts/check_docker_env.sh"
    echo ""
    echo "⚠️  IMPORTANT: Toujours exporter DATABASE_URL avant de lancer l'API!"
    echo "📚 Documentation: http://localhost:8000/docs"
}

# Exécution
main "$@"