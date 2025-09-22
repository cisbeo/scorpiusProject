#!/bin/bash

# Script de correction base de données - Scorpius Project
# Usage: ./scripts/fix_database.sh [local|production]

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

# Fix local database (Docker)
fix_local_database() {
    log "🔧 Correction base de données locale (Docker)..."

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        error "Docker n'est pas démarré"
        exit 1
    fi

    # Check if services are running
    if ! docker-compose ps | grep -q "db.*Up"; then
        warning "PostgreSQL n'est pas démarré, lancement..."
        docker-compose up -d db
        sleep 10
    fi

    # Check current tables
    info "Vérification tables existantes..."
    CURRENT_TABLES=$(docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "\dt" | grep -c "table" || echo "0")
    log "Tables actuelles: $CURRENT_TABLES"

    if [[ $CURRENT_TABLES -lt 9 ]]; then
        warning "Tables manquantes détectées, correction en cours..."

        # Apply fix with all models
        log "Application du script de correction..."
        docker-compose run --rm app python -c "
import asyncio
from src.db.session import async_engine
from src.db.base import Base
# CRITICAL: Import all models to ensure they are registered
from src.models import *

async def fix_database():
    try:
        # Create all missing tables
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Toutes les tables vérifiées/créées')

        # List final tables
        from sqlalchemy import text
        async with async_engine.connect() as conn:
            result = await conn.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public'\"))
            tables = [row[0] for row in result]
            print(f'📊 Tables finales ({len(tables)}): {', '.join(sorted(tables))}')

    except Exception as e:
        print(f'❌ Erreur: {e}')
        import traceback
        traceback.print_exc()
        exit(1)

asyncio.run(fix_database())
"

        # Verify fix
        FINAL_TABLES=$(docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "\dt" | grep -c "table" || echo "0")

        if [[ $FINAL_TABLES -ge 9 ]]; then
            log "✅ Correction réussie: $FINAL_TABLES tables créées"
        else
            error "❌ Correction échouée: seulement $FINAL_TABLES tables"
            exit 1
        fi
    else
        log "✅ Base de données locale OK ($CURRENT_TABLES tables)"
    fi

    # Test database connection
    info "Test connexion base de données..."
    docker-compose run --rm app python -c "
import asyncio
from src.db.session import get_async_db

async def test_connection():
    try:
        async for db in get_async_db():
            print('✅ Connexion base de données OK')
            break
    except Exception as e:
        print(f'❌ Erreur connexion: {e}')
        exit(1)

asyncio.run(test_connection())
"
}

# Fix production database
fix_production_database() {
    log "🔧 Correction base de données production..."

    # Check SSH key
    if [[ ! -f ~/.ssh/scorpiusProjectPrivateKey.txt ]]; then
        error "Clé SSH non trouvée: ~/.ssh/scorpiusProjectPrivateKey.txt"
        exit 1
    fi

    # Backup production database first
    warning "Sauvegarde de la base de production..."
    ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 \
        "sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U scorpius scorpius_prod > /tmp/backup_before_fix_$(date +%Y%m%d_%H%M%S).sql'"

    log "✅ Sauvegarde créée"

    # Check current state
    info "Vérification état actuel..."
    PROD_TABLES=$(ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 \
        "sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T postgres psql -U scorpius -d scorpius_prod -c \"\\dt\"'" | grep -c "table" || echo "0")

    log "Tables production actuelles: $PROD_TABLES"

    if [[ $PROD_TABLES -lt 9 ]]; then
        warning "Tables manquantes en production, correction..."

        # Apply fix to production
        ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 \
            "sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T api python -c \"
import asyncio
from src.db.session import async_engine
from src.db.base import Base
# CRITICAL: Import all models
from src.models import *

async def fix_prod_database():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Production database fixed')
    except Exception as e:
        print(f'❌ Error: {e}')
        exit(1)

asyncio.run(fix_prod_database())
\"'"

        # Verify production fix
        FINAL_PROD_TABLES=$(ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 \
            "sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T postgres psql -U scorpius -d scorpius_prod -c \"\\dt\"'" | grep -c "table" || echo "0")

        if [[ $FINAL_PROD_TABLES -ge 9 ]]; then
            log "✅ Production corrigée: $FINAL_PROD_TABLES tables"
        else
            error "❌ Correction production échouée"
            exit 1
        fi
    else
        log "✅ Base de données production OK ($PROD_TABLES tables)"
    fi

    # Test production registration
    info "Test enregistrement production..."
    REGISTER_TEST=$(curl -k -s -X POST https://scorpius.bbmiss.co/api/v1/auth/register \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test-fix@scorpius.fr",
            "password": "TestPass1!",
            "full_name": "Test Fix User",
            "role": "bid_manager"
        }')

    if echo "$REGISTER_TEST" | grep -q '"id"'; then
        log "✅ Test enregistrement production OK"
    else
        warning "⚠️ Test enregistrement: ${REGISTER_TEST:0:100}..."
    fi
}

# Show database info
show_database_info() {
    local env="$1"

    log "📊 Informations base de données ($env)..."

    if [[ "$env" == "local" ]]; then
        if docker-compose ps | grep -q "db.*Up"; then
            echo
            info "=== Tables locales ==="
            docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "\dt"
            echo
            info "=== Taille base locale ==="
            docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "SELECT pg_size_pretty(pg_database_size('scorpius_mvp'));"
        else
            warning "Services Docker non démarrés"
        fi

    elif [[ "$env" == "production" ]]; then
        if [[ -f ~/.ssh/scorpiusProjectPrivateKey.txt ]]; then
            echo
            info "=== Tables production ==="
            ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 \
                "sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T postgres psql -U scorpius -d scorpius_prod -c \"\\dt\"'"
            echo
            info "=== Taille base production ==="
            ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 \
                "sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T postgres psql -U scorpius -d scorpius_prod -c \"SELECT pg_size_pretty(pg_database_size('scorpius_prod'));\"'"
        else
            error "Clé SSH non trouvée"
        fi
    fi
}

# Main script logic
case "${1:-}" in
    local)
        fix_local_database
        ;;
    production)
        fix_production_database
        ;;
    info-local)
        show_database_info "local"
        ;;
    info-production)
        show_database_info "production"
        ;;
    *)
        echo "Script de correction base de données - Scorpius Project"
        echo
        echo "Usage: $0 {local|production|info-local|info-production}"
        echo
        echo "Commandes:"
        echo "  local           - Corrige la base de données Docker locale"
        echo "  production      - Corrige la base de données production (avec backup)"
        echo "  info-local      - Affiche infos base locale"
        echo "  info-production - Affiche infos base production"
        echo
        echo "Problème résolu:"
        echo "  Tables manquantes causées par l'importation incomplète des modèles"
        echo "  lors de Base.metadata.create_all()"
        echo
        echo "Solution:"
        echo "  Import explicite de tous les modèles via 'from src.models import *'"
        echo "  avant d'appeler create_all()"
        echo
        echo "Tables attendues (9):"
        echo "  users, audit_logs, company_profiles, procurement_documents,"
        echo "  bid_responses, capability_matches, compliance_checks,"
        echo "  extracted_requirements, processing_events"
        ;;
esac