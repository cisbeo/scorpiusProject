#!/bin/bash

# Start Test Environment for Multi-Document Analysis
# =================================================

set -e  # Exit on error

echo "🚀 Starting Scorpius Test Environment"
echo "======================================"

# Check if we're in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found. Make sure you're in the project root."
    exit 1
fi

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

echo "📋 Step 1: Stopping any existing services..."
docker-compose down --remove-orphans

echo "📋 Step 2: Starting PostgreSQL and Redis..."
docker-compose up -d db redis

echo "📋 Step 3: Waiting for database to be ready..."
sleep 10

# Check database connectivity
echo "📋 Step 4: Verifying database connection..."
docker-compose exec -T db pg_isready -U scorpius -d scorpius_mvp
if [ $? -ne 0 ]; then
    echo "❌ Database connection failed"
    exit 1
fi

echo "📋 Step 5: Starting API service..."
docker-compose up -d app

echo "📋 Step 6: Waiting for API to be ready..."
sleep 15

# Check API health
MAX_RETRIES=12
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "✅ API is healthy!"
        break
    else
        echo "⏳ Waiting for API... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 5
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ API failed to start within timeout"
    echo "📋 Checking API logs..."
    docker-compose logs --tail=20 app
    exit 1
fi

echo "📋 Step 7: Verifying test documents..."
if [ ! -f "Examples/VSGP-AO/RC.pdf" ] || [ ! -f "Examples/VSGP-AO/CCAP.pdf" ] || [ ! -f "Examples/VSGP-AO/CCTP.pdf" ]; then
    echo "⚠️ Warning: Some test documents are missing in Examples/VSGP-AO/"
    ls -la Examples/VSGP-AO/
    echo "Tests will skip missing documents."
fi

echo "📋 Step 8: Installing Python test dependencies..."
if [ -f "venv_py311/bin/activate" ]; then
    source venv_py311/bin/activate
    pip install httpx pytest pytest-asyncio
    echo "✅ Dependencies installed"
else
    echo "⚠️ Virtual environment not found. Installing globally..."
    pip install httpx pytest pytest-asyncio
fi

echo "✅ Test Environment Ready!"
echo "=========================="
echo "🌐 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/api/v1/docs"
echo "🐘 pgAdmin: http://localhost:5050 (admin@admin.com / admin)"
echo ""
echo "🧪 To run tests:"
echo "   python test_multi_document_analysis.py"
echo ""
echo "🔍 To check services:"
echo "   docker-compose ps"
echo ""
echo "📋 To view logs:"
echo "   docker-compose logs -f app"