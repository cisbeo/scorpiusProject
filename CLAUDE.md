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