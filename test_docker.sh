#!/bin/bash

# Script de test Docker - Scorpius Project
# Usage: ./test_docker.sh [start|test|reset|logs]

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

# Start Docker environment
start_docker() {
    log "🐳 Démarrage environnement Docker Scorpius..."

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        error "Docker n'est pas démarré. Lancez Docker Desktop."
        exit 1
    fi

    # Create necessary directories
    mkdir -p uploads temp logs nginx/ssl

    # Start services
    log "Démarrage des services PostgreSQL et Redis..."
    docker-compose up -d db redis

    # Wait for PostgreSQL to be ready
    log "Attente démarrage PostgreSQL..."
    for i in {1..30}; do
        if docker-compose exec -T db pg_isready -U scorpius -d scorpius_mvp > /dev/null 2>&1; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            error "PostgreSQL n'a pas démarré dans les temps"
            exit 1
        fi
        sleep 2
    done

    log "✅ PostgreSQL prêt"

    # Initialize database with all tables
    log "Initialisation base de données avec tous les modèles..."
    docker-compose run --rm app python -c "
import asyncio
from src.db.session import async_engine
from src.db.base import Base
# Import all models to ensure they are registered
from src.models import *

async def ensure_all_tables():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Toutes les tables vérifiées/créées')
    except Exception as e:
        print(f'❌ Erreur: {e}')
        exit(1)

asyncio.run(ensure_all_tables())
"

    # Start API
    log "Démarrage API..."
    docker-compose up -d app

    # Wait for API to be ready
    log "Attente démarrage API..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            error "API n'a pas démarré dans les temps"
            exit 1
        fi
        sleep 2
    done

    log "✅ Environnement Docker démarré avec succès !"
    info "Services disponibles:"
    info "- API: http://localhost:8000"
    info "- Documentation: http://localhost:8000/docs"
    info "- pgAdmin: http://localhost:5050 (admin@scorpiusproject.fr / admin)"
    info "- PostgreSQL: localhost:5432"
    info "- Redis: localhost:6379"
}

# Test Docker environment
test_docker() {
    log "🧪 Tests environnement Docker Scorpius..."

    # Verify services are running
    if ! docker-compose ps | grep -q "Up"; then
        error "Services Docker non démarrés. Lancez d'abord: ./test_docker.sh start"
        exit 1
    fi

    # Test API health
    echo
    info "Test de santé API..."
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
    if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
        log "✅ API health OK"
    else
        error "❌ API health failed: $HEALTH_RESPONSE"
        return 1
    fi

    # Test database tables
    echo
    info "Vérification tables PostgreSQL..."
    TABLES=$(docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "\\dt" | grep -c "table" || echo "0")
    if [[ $TABLES -ge 9 ]]; then
        log "✅ Base de données: $TABLES tables trouvées"
    else
        warning "⚠️ Base de données: seulement $TABLES tables (attendu: 9)"
    fi

    # Test user registration (with working password)
    echo
    info "Test enregistrement utilisateur..."
    REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test-docker@example.com",
            "password": "TestPass1!",
            "full_name": "Test Docker User",
            "role": "bid_manager"
        }')

    if echo "$REGISTER_RESPONSE" | grep -q '"id"'; then
        log "✅ Enregistrement utilisateur OK"
    else
        warning "⚠️ Enregistrement failed (peut-être utilisateur existe déjà): ${REGISTER_RESPONSE:0:100}..."
    fi

    # Test user login
    echo
    info "Test connexion utilisateur..."
    LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test-docker@example.com",
            "password": "TestPass1!"
        }')

    if echo "$LOGIN_RESPONSE" | grep -q '"access_token"'; then
        log "✅ Connexion utilisateur OK"

        # Extract token for further tests
        TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['tokens']['access_token'])
except:
    print('')
")

        if [[ -n "$TOKEN" ]]; then
            # Test GET /me endpoint (authentication middleware)
            echo
            info "Test GET /me (middleware authentification)..."
            ME_RESPONSE=$(curl -s -X GET http://localhost:8000/api/v1/auth/me \
                -H "Authorization: Bearer $TOKEN")

            if echo "$ME_RESPONSE" | grep -q '"id"'; then
                log "✅ GET /me fonctionne - authentification middleware OK"
            else
                error "❌ GET /me échoue - problème middleware authentification"
                echo "Response: $ME_RESPONSE"
                echo "Token (50 premiers chars): ${TOKEN:0:50}..."
            fi

            # Test protected endpoint (company profile creation)
            echo
            info "Test endpoint protégé (création profil entreprise)..."
            COMPANY_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/company-profile \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d '{
                    "company_name": "Test Docker Company",
                    "siret": "12345678901234",
                    "description": "Company for Docker testing"
                }')

            if echo "$COMPANY_RESPONSE" | grep -q '"id"'; then
                log "✅ Création profil entreprise OK"
            else
                warning "⚠️ Création profil entreprise failed: ${COMPANY_RESPONSE:0:100}..."
            fi
        fi

    else
        error "❌ Connexion failed: ${LOGIN_RESPONSE:0:100}..."
    fi

    echo
    log "🎉 Tests Docker terminés !"
    info "Pour plus de tests, utilisez la documentation interactive:"
    info "http://localhost:8000/docs"
}

# Reset Docker environment
reset_docker() {
    log "🔄 Reset environnement Docker..."

    docker-compose down -v
    docker-compose build --no-cache

    log "✅ Environnement reset"
    info "Relancez avec: ./test_docker.sh start"
}

# Show logs
show_logs() {
    info "📋 Logs des services Docker..."
    echo
    info "=== API Logs ==="
    docker-compose logs --tail=20 app
    echo
    info "=== PostgreSQL Logs ==="
    docker-compose logs --tail=10 db
    echo
    info "=== Redis Logs ==="
    docker-compose logs --tail=10 redis
}

# Show status
show_status() {
    log "📊 Statut environnement Docker..."
    echo
    info "=== Services Status ==="
    docker-compose ps
    echo
    info "=== Docker Images ==="
    docker images | grep scorpius || echo "Aucune image Scorpius trouvée"
    echo
    info "=== Docker Volumes ==="
    docker volume ls | grep scorpius || echo "Aucun volume Scorpius trouvé"
}

# Main script logic
case "${1:-}" in
    start)
        start_docker
        ;;
    test)
        test_docker
        ;;
    reset)
        reset_docker
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    *)
        echo "Script de test Docker - Scorpius Project"
        echo
        echo "Usage: $0 {start|test|reset|logs|status}"
        echo
        echo "Commandes:"
        echo "  start   - Démarre l'environnement Docker complet"
        echo "  test    - Lance les tests fonctionnels"
        echo "  reset   - Reset complet (supprime volumes et rebuild)"
        echo "  logs    - Affiche les logs des services"
        echo "  status  - Affiche le statut des services"
        echo
        echo "Workflow recommandé:"
        echo "  1. ./test_docker.sh start    # Première fois"
        echo "  2. ./test_docker.sh test     # Vérifier fonctionnement"
        echo "  3. ./test_docker.sh logs     # Si problème"
        echo
        echo "En cas de problème:"
        echo "  ./test_docker.sh reset && ./test_docker.sh start"
        ;;
esac