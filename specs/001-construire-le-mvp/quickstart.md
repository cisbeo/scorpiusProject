# MVP Quickstart Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 6+
- Docker & Docker Compose (optional)

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/scorpiusproject/backend.git
cd backend
```

### 2. Setup Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

### 4. Database Setup
```bash
# Create database
createdb scorpius_mvp

# Run migrations
alembic upgrade head

# Enable pgvector extension (for future use)
psql -d scorpius_mvp -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 5. Redis Setup
```bash
# Start Redis (if not using Docker)
redis-server
```

### 6. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```env
DATABASE_URL=postgresql://user:pass@localhost/scorpius_mvp
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
MAX_UPLOAD_SIZE=52428800  # 50MB in bytes
UPLOAD_PATH=/app/uploads
LOG_LEVEL=INFO
```

## Quick Start with Docker

```bash
# Build and start all services
docker-compose up -d

# Run migrations
docker-compose exec app alembic upgrade head

# Create admin user
docker-compose exec app python scripts/create_admin.py
```

## API Testing Workflow

### 1. Register User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "bid.manager@company.fr",
    "password": "SecurePass123!",
    "full_name": "Jean Dupont",
    "role": "bid_manager"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "bid.manager@company.fr",
    "password": "SecurePass123!"
  }'

# Save the access_token from response
export TOKEN="your-access-token-here"
```

### 3. Setup Company Profile
```bash
curl -X PUT http://localhost:8000/api/v1/company-profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "TechSolutions SARL",
    "siret": "12345678901234",
    "description": "ESN spécialisée en développement web et mobile",
    "capabilities": [
      {
        "name": "Développement Web",
        "keywords": ["PHP", "Python", "JavaScript", "React", "FastAPI"]
      },
      {
        "name": "Infrastructure Cloud",
        "keywords": ["AWS", "Azure", "Docker", "Kubernetes"]
      }
    ],
    "certifications": [
      {
        "name": "ISO 9001:2015",
        "valid_until": "2025-12-31"
      },
      {
        "name": "Qualiopi",
        "valid_until": "2026-06-30"
      }
    ],
    "team_size": 50,
    "annual_revenue": 5000000
  }'
```

### 4. Upload Procurement Document
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/procurement.pdf"

# Save document_id from response
export DOC_ID="document-uuid-here"
```

### 5. Process Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/process \
  -H "Authorization: Bearer $TOKEN"

# Check processing status
curl -X GET http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $TOKEN"
```

### 6. View Extracted Requirements
```bash
curl -X GET http://localhost:8000/api/v1/documents/$DOC_ID/requirements \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Analyze Capability Match
```bash
curl -X POST http://localhost:8000/api/v1/analysis/match \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\": \"$DOC_ID\"}"
```

### 8. Generate Bid Response
```bash
curl -X POST http://localhost:8000/api/v1/bid-responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "'$DOC_ID'",
    "response_type": "complete"
  }'

# Save bid_id from response
export BID_ID="bid-uuid-here"
```

### 9. Check Compliance
```bash
curl -X POST http://localhost:8000/api/v1/bid-responses/$BID_ID/compliance \
  -H "Authorization: Bearer $TOKEN"
```

### 10. Download Final Response
```bash
curl -X GET http://localhost:8000/api/v1/bid-responses/$BID_ID/download?format=pdf \
  -H "Authorization: Bearer $TOKEN" \
  -o bid_response.pdf
```

## Development Tools

### Run Tests
```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# Contract tests
pytest tests/contract -v

# All tests with coverage
pytest --cov=src --cov-report=html
```

### Code Quality
```bash
# Linting
ruff check src tests

# Type checking
mypy src

# Security scan
bandit -r src

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI Schema: http://localhost:8000/openapi.json

## Monitoring

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Logs
```bash
# Application logs
tail -f logs/app.log

# With Docker
docker-compose logs -f app
```

### Database Monitoring
```bash
# Connection pool status
psql -d scorpius_mvp -c "SELECT * FROM pg_stat_activity WHERE datname='scorpius_mvp';"

# Slow queries
psql -d scorpius_mvp -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

## Troubleshooting

### Common Issues

1. **PDF Processing Fails**
   - Check file size < 50MB
   - Verify PDF is not corrupted
   - Check logs for specific error

2. **Authentication Errors**
   - Verify JWT token not expired
   - Check token format: "Bearer <token>"
   - Refresh token if needed

3. **Database Connection Issues**
   - Verify PostgreSQL is running
   - Check DATABASE_URL in .env
   - Verify database exists and migrations ran

4. **Performance Issues**
   - Check Redis is running for caching
   - Monitor database connection pool
   - Review slow query logs

## MVP Limitations

Current MVP does not include:
- Advanced NLP (uses keyword matching)
- Multi-document processing
- Collaborative features
- External integrations
- Custom templates
- Historical analytics

These features are prepared in the architecture for future implementation.

## Support

- Documentation: /docs/
- API Issues: Check /api/v1/health
- Logs: /logs/app.log
- Database: Check migration status with `alembic current`