#!/bin/bash

# Script d'Exécution Complète des Tests Multi-Documents
# ====================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo "🧪 Scorpius Multi-Document Analysis - Test Suite"
echo "==============================================="

# Navigate to project root
cd ../..

# 1. Start environment
log_info "Starting test environment..."
cd tests/testComplet
if [ -f "start_test_environment_robust.sh" ]; then
    chmod +x start_test_environment_robust.sh
    ./start_test_environment_robust.sh
else
    log_error "Startup script not found"
    exit 1
fi

# 2. Wait a bit for full startup
sleep 5

# 3. Run basic validation
log_info "Running basic endpoint validation..."
python test_endpoints_basic.py
echo ""

# 4. Run complete multi-document test
log_info "Running complete multi-document analysis test..."
python test_multi_document_analysis.py
echo ""

# 5. Show final status
log_info "Final API health check..."
curl -s http://localhost:8000/api/v1/health | python -m json.tool || echo "API not responding"

echo ""
log_info "🎉 Test suite completed!"
echo "Check generated report files for detailed results."
echo ""
echo "📋 To stop environment:"
echo "   cd ../.. && docker-compose down"