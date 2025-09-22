# Claude Development Context

## Project Overview
French public procurement bid management MVP backend with evolutionary architecture for future NLP, multi-tenancy, and collaborative features.

## Tech Stack
- **Language**: Python 3.11
- **Framework**: FastAPI 0.109+
- **Database**: PostgreSQL 15+ with pgvector
- **Cache**: Redis 6+
- **Testing**: pytest, pytest-asyncio
- **Docs**: OpenAPI/Swagger

## Architecture Patterns
- Hexagonal Architecture with DDD
- Repository Pattern for data access
- Strategy Pattern for processors
- Event-driven document pipeline
- Plugin architecture for extensibility

## Key Directories
```
src/
├── api/          # FastAPI endpoints
├── core/         # Business logic
├── models/       # SQLAlchemy models
├── services/     # Application services
├── repositories/ # Data access layer
└── processors/   # Document processors

tests/
├── unit/         # Isolated tests
├── integration/  # API tests
└── contract/     # OpenAPI validation
```

## Development Principles
1. **TDD**: Write failing tests first
2. **API-First**: All features via REST
3. **Type Safety**: Use Pydantic models
4. **Async First**: Use async/await
5. **Clean Code**: Single responsibility

## Constitutional Requirements
- Idempotent document processing
- Structured logging with trace IDs
- JWT authentication with refresh
- Connection pooling for databases
- <200ms API response target

## Testing Commands
```bash
pytest tests/unit -v        # Unit tests
pytest tests/integration -v # API tests
pytest --cov=src            # Coverage
```

## Code Quality
```bash
ruff check src tests  # Linting
mypy src             # Type checking
bandit -r src        # Security
```

## Production Server Access

### SSH Connection
```bash
ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162
```

### Server Details
- **Host**: scorpius.bbmiss.co (IP: 83.228.208.162)
- **User**: ubuntu (puis sudo -u scorpius pour les opérations)
- **Project Path**: /home/scorpius/scorpiusProject
- **Provider**: Infomaniak

### Common Production Commands
```bash
# Se connecter au serveur
ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162

# Changer vers l'utilisateur scorpius pour les opérations Docker
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && [COMMAND]'

# Voir les logs de l'API
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml logs -f api'

# Redémarrer les services
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml restart api'

# Exécuter des commandes dans le conteneur API
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T api [COMMAND]'

# Initialiser/réinitialiser la base de données
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T api python /app/scripts/init_db.py'

# Vérifier les tables PostgreSQL
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml exec -T postgres psql -U scorpius -d scorpius_prod -c "\\dt"'
```

### File Transfer to Production
```bash
# Copier un fichier vers le serveur (zone temporaire)
scp -i ~/.ssh/scorpiusProjectPrivateKey.txt [LOCAL_FILE] ubuntu@83.228.208.162:/tmp/

# Puis déplacer vers le bon emplacement avec les bonnes permissions
ssh -i ~/.ssh/scorpiusProjectPrivateKey.txt ubuntu@83.228.208.162 "sudo mv /tmp/[FILE] /home/scorpius/scorpiusProject/[PATH] && sudo chown scorpius:scorpius /home/scorpius/scorpiusProject/[PATH]"
```

### Docker Compose Operations
```bash
# Arrêter tous les services
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml down'

# Démarrer tous les services
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml up -d'

# Recréer un service spécifique (ex: API)
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml down api && docker-compose -f docker-compose.prod.yml up -d api'

# Voir le statut des conteneurs
sudo -u scorpius bash -c 'cd /home/scorpius/scorpiusProject && docker-compose -f docker-compose.prod.yml ps'
```

## Common Tasks

### Add New Endpoint
1. Define OpenAPI contract first
2. Create Pydantic schemas
3. Write integration test
4. Implement endpoint
5. Add unit tests

### Add Document Processor
1. Implement DocumentProcessor interface
2. Register in ProcessorFactory
3. Add integration test
4. Update pipeline configuration

### Database Migration
```bash
alembic revision -m "description"
# Edit migration file
alembic upgrade head
```

## Performance Tips
- Use `select_related` for joins
- Implement pagination everywhere
- Cache expensive computations
- Use async for I/O operations
- Profile with `py-spy` if slow

## Security Checklist
- [ ] Validate all inputs
- [ ] Sanitize file uploads
- [ ] Use parameterized queries
- [ ] Hash passwords with bcrypt
- [ ] Validate JWT signatures
- [ ] Rate limit endpoints
- [ ] Log security events

## Error Handling
- Use custom exceptions
- Return structured errors
- Log full stack traces
- Include request IDs
- User-friendly messages

## Future Preparation
- Tenant ID in all models (nullable)
- Vector embeddings table ready
- Event sourcing for audit
- Plugin interfaces defined
- Versioned API endpoints

## Recent Changes
- Added evolutionary architecture design
- Implemented plugin system for processors
- Prepared vector database support
- Deployed MVP to production (scorpius.bbmiss.co)
- Added GET /me endpoint for user profile
- Fixed PyJWT dependency issue in production

## Current Status (2025-09-22)

### ✅ Working - Local Development Environment
- **Docker environment fully configured**
  - PostgreSQL database with all 9 tables properly initialized
  - Redis cache service
  - API container with hot-reload capability
  - pgAdmin interface (http://localhost:5050)
- **Authentication (Local)**
  - User registration (POST /auth/register) ✅
  - User login (POST /auth/login) ✅
  - Token generation and refresh ✅
  - JWT tokens properly signed and formatted
- **Database Schema**
  - All models properly created: users, audit_logs, company_profiles, procurement_documents, bid_responses, capability_matches, compliance_checks, extracted_requirements, processing_events

### ✅ Working - Production Environment
- Production deployment on https://scorpius.bbmiss.co
- Basic infrastructure (PostgreSQL, Redis, Nginx with SSL)
- Health check endpoint

### 🔴 Issues Resolved in Local
1. **Database Initialization Issue** ✅ FIXED
   - **Problem**: Tables not created during initial DB setup
   - **Cause**: Models not properly imported during Base.metadata.create_all()
   - **Solution**: Explicit import of all models in initialization script
   - **Impact**: All 9 tables now properly created in both local and can be applied to production

2. **Password Validation Issue** ✅ FIXED
   - **Problem**: "Password should not contain sequential characters" error
   - **Cause**: Too restrictive password validation rejecting valid passwords
   - **Solution**: Use simpler compliant passwords (e.g., "TestPass1!" instead of "TestPassword123!")
   - **Impact**: User registration now works in local environment

### 🔴 Issues Resolved Today
1. **Authentication Middleware Problem** ✅ FIXED (Local)
   - **Problem**: `get_current_user` dependency not properly validating JWT tokens
   - **Root Cause**: Missing `Depends(HTTPBearer())` to extract Authorization header
   - **Solution**: Added `credentials: HTTPAuthorizationCredentials = Depends(security)` to all auth functions
   - **Location**: src/middleware/auth.py
   - **Status**: ✅ Local working, needs application to production

### 🔴 Issues to Fix
1. **Production Synchronization**
   - Apply authentication middleware fix to production
   - Apply database initialization fix to production
   - Verify all tables exist in production PostgreSQL

2. **Test Coverage & Features**
   - Document upload/processing not tested
   - Company profile CRUD not tested
   - Capability matching analysis not tested

## Next Session Tasks

### Priority 1: Production Synchronization
1. **Apply authentication middleware fix to production**
   - Deploy corrected src/middleware/auth.py
   - Test GET /me and protected endpoints in production
   - Verify JWT authentication works end-to-end
2. **Apply database fixes to production**
   - Backup production database before changes
   - Run database initialization script with all models
   - Verify all 9 tables exist in production

### Priority 2: Complete MVP Testing
1. **Test protected endpoints functionality**
   - Document upload endpoint (POST /documents)
   - Company profile CRUD operations
   - Capability matching analysis
   - File processing pipeline validation
2. **Verify business logic**
   - Document analysis functionality
   - Recommendation engine accuracy
   - Scoring algorithms validation

### Priority 3: Production Improvements
1. Set up monitoring (logs aggregation)
2. Configure automated backups
3. Implement rate limiting
4. Add health metrics endpoint
5. Set up CI/CD pipeline

## Database Initialization Fix

### Script to Create All Tables
```python
# Run this in Docker container to ensure all tables exist
import asyncio
from src.db.session import async_engine
from src.db.base import Base
# Import all models to ensure they are registered
from src.models import *

async def ensure_all_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('✅ All tables verified/created')

asyncio.run(ensure_all_tables())
```

## Known Working Test Users

### Local Development
- Email: test-fixed@example.com
- Password: TestPass1!
- Status: ✅ Registered and login working

### Production (needs verification)
- Email: test-production@scorpius.fr
- Password: TestProd2024!
- Status: ⚠️ May need re-registration after DB fix