#!/bin/bash

# Script de Démarrage depuis le répertoire testComplet
# ===================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo "🚀 Starting Scorpius Test Environment from testComplet"
echo "====================================================="

# Navigate to project root
cd ../..

# Check prerequisites
if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker not found. Please install Docker first."
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker first."
    exit 1
fi

log_info "Prerequisites checked"

# Clean start
log_info "Cleaning previous environment..."
docker-compose down --remove-orphans --volumes 2>/dev/null || true
sleep 2

# Start database and Redis
log_info "Starting database and Redis..."
docker-compose up -d db redis

# Wait for database
log_info "Waiting for database to be ready..."
MAX_WAIT=60
COUNT=0

while [ $COUNT -lt $MAX_WAIT ]; do
    if docker-compose exec -T db pg_isready -U scorpius -d scorpius_mvp > /dev/null 2>&1; then
        log_info "Database is ready!"
        break
    else
        echo "⏳ Waiting for database... ($((COUNT + 1))/$MAX_WAIT)"
        sleep 2
        COUNT=$((COUNT + 1))
    fi
done

if [ $COUNT -eq $MAX_WAIT ]; then
    log_error "Database failed to start"
    exit 1
fi

# Ensure database exists
if ! docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "SELECT 1;" > /dev/null 2>&1; then
    log_warn "Creating database..."
    docker-compose exec -T db createdb -U scorpius scorpius_mvp 2>/dev/null || true
fi

# Build and start API
log_info "Building and starting API..."
docker-compose build app
docker-compose up -d app

# Wait for API
log_info "Waiting for API..."
COUNT=0
while [ $COUNT -lt 60 ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_info "API is ready!"
        break
    else
        echo "⏳ Waiting for API... ($((COUNT + 1))/60)"
        sleep 2
        COUNT=$((COUNT + 1))
    fi
done

if [ $COUNT -eq 60 ]; then
    log_error "API failed to start"
    exit 1
fi

# Initialize database
log_info "Initializing database..."
if docker-compose exec -T app python /app/scripts/init_db_complete.py; then
    log_info "Database initialized"
else
    log_warn "Database initialization had issues"
fi

# Final status
log_info "Environment ready!"
echo ""
echo "🌐 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/api/v1/docs"
echo ""
echo "🧪 Run tests from testComplet directory:"
echo "   cd tests/testComplet"
echo "   python test_endpoints_basic.py"
echo "   python test_multi_document_analysis.py"
echo ""
echo "🛑 Stop: docker-compose down"