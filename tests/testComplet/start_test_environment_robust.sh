#!/bin/bash

# Script de Démarrage Robuste pour Tests Multi-Documents
# =====================================================

set -e  # Exit on error

echo "🚀 Starting Robust Scorpius Test Environment"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

if ! command_exists docker; then
    log_error "Docker not found. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    log_error "Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker first."
    exit 1
fi

log_info "All prerequisites met"

# Clean start
echo "📋 Step 2: Clean restart of all services..."
docker-compose down --remove-orphans --volumes
sleep 2

# Start database and redis first
echo "📋 Step 3: Starting database and Redis..."
docker-compose up -d db redis

# Wait for database to be ready with proper health check
echo "📋 Step 4: Waiting for database to be ready..."
MAX_DB_WAIT=60
DB_WAIT_COUNT=0

while [ $DB_WAIT_COUNT -lt $MAX_DB_WAIT ]; do
    if docker-compose exec -T db pg_isready -U scorpius -d scorpius_mvp > /dev/null 2>&1; then
        log_info "Database is ready!"
        break
    else
        echo "⏳ Waiting for database... ($((DB_WAIT_COUNT + 1))/$MAX_DB_WAIT)"
        sleep 2
        DB_WAIT_COUNT=$((DB_WAIT_COUNT + 1))
    fi
done

if [ $DB_WAIT_COUNT -eq $MAX_DB_WAIT ]; then
    log_error "Database failed to start within timeout"
    echo "📋 Database logs:"
    docker-compose logs --tail=10 db
    exit 1
fi

# Check if database exists, if not create it
echo "📋 Step 5: Ensuring database exists..."
if ! docker-compose exec -T db psql -U scorpius -d scorpius_mvp -c "SELECT 1;" > /dev/null 2>&1; then
    log_warn "Database doesn't exist, creating it..."
    docker-compose exec -T db createdb -U scorpius scorpius_mvp || log_warn "Database might already exist"
fi

# Build and start API
echo "📋 Step 6: Building and starting API..."
docker-compose build app
docker-compose up -d app

# Wait for API to be healthy
echo "📋 Step 7: Waiting for API to be ready..."
MAX_API_WAIT=120  # 2 minutes
API_WAIT_COUNT=0

while [ $API_WAIT_COUNT -lt $MAX_API_WAIT ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_info "API is responding!"
        break
    else
        echo "⏳ Waiting for API... ($((API_WAIT_COUNT + 1))/$MAX_API_WAIT)"
        sleep 2
        API_WAIT_COUNT=$((API_WAIT_COUNT + 1))
    fi
done

if [ $API_WAIT_COUNT -eq $MAX_API_WAIT ]; then
    log_error "API failed to start within timeout"
    echo "📋 API logs:"
    docker-compose logs --tail=20 app
    exit 1
fi

# Initialize database tables
echo "📋 Step 8: Initializing database tables..."
if docker-compose exec -T app python /app/scripts/init_db_complete.py; then
    log_info "Database tables initialized successfully"
else
    log_warn "Database initialization had issues, continuing..."
fi

# Verify API health
echo "📋 Step 9: Final health check..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/v1/health)
if echo "$HEALTH_RESPONSE" | grep -q '"status"'; then
    log_info "API health check passed"
    echo "📊 Health Status:"
    echo "$HEALTH_RESPONSE" | python -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    log_warn "API responding but health check format unexpected"
fi

# Verify test documents
echo "📋 Step 10: Verifying test documents..."
DOCS_DIR="Examples/VSGP-AO"
if [ -d "$DOCS_DIR" ]; then
    MISSING_DOCS=""
    for doc in "RC.pdf" "CCAP.pdf" "CCTP.pdf"; do
        if [ ! -f "$DOCS_DIR/$doc" ]; then
            MISSING_DOCS="$MISSING_DOCS $doc"
        fi
    done

    if [ -z "$MISSING_DOCS" ]; then
        log_info "All test documents found"
    else
        log_warn "Missing test documents:$MISSING_DOCS"
    fi
else
    log_warn "Test documents directory not found: $DOCS_DIR"
fi

# Install Python test dependencies on host
echo "📋 Step 11: Installing Python test dependencies..."
if command_exists pip; then
    pip install httpx pytest pytest-asyncio > /dev/null 2>&1 || pip install --user httpx pytest pytest-asyncio
    log_info "Python dependencies installed"
else
    log_warn "pip not found, manual installation may be required"
fi

echo ""
log_info "🎉 Robust Test Environment Ready!"
echo "================================="
echo "🌐 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/api/v1/docs"
echo "🐘 Database: localhost:5432 (scorpius/scorpius)"
echo "🗄️ Redis: localhost:6379"
echo ""
echo "🧪 Run tests:"
echo "   python test_multi_document_analysis.py"
echo "   python test_endpoints_basic.py"
echo ""
echo "🔍 Monitor services:"
echo "   docker-compose ps"
echo "   docker-compose logs -f app"
echo "   docker-compose logs -f db"
echo ""
echo "🛑 Stop environment:"
echo "   docker-compose down"