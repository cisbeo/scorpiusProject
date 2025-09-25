# Docker Environment Initialization Guide

## Overview

The Scorpius Project Docker environment has been fully automated with robust initialization scripts that handle all setup steps, port conflicts, and database initialization. This guide documents the complete workflow.

## Quick Start

### One-Command Setup

```bash
# Complete initialization with automatic API startup
./scripts/init_docker_env.sh --clean --start-api
```

This single command will:
1. Clean any existing Docker environment
2. Start PostgreSQL (with automatic port detection)
3. Start Redis cache
4. Initialize all database tables
5. Create test users
6. Export DATABASE_URL
7. Start the API server

## Scripts Overview

### 1. `scripts/init_docker_env.sh`

The main initialization script that orchestrates the entire setup process.

**Features:**
- Automatic port detection (5434→5435→5436→5437→5438)
- Clean mode to reset environment
- Interactive and non-interactive modes
- DATABASE_URL export
- Integrated API startup
- Comprehensive error handling

**Options:**
```bash
--clean       # Clean existing environment before setup
--verbose     # Show detailed output
--start-api   # Automatically start API after initialization
--no-prompt   # Skip interactive prompts
--help        # Show help message
```

### 2. `scripts/check_docker_env.sh`

Verification script to validate the Docker environment status.

**Checks:**
- Docker daemon availability
- Container status (PostgreSQL, Redis)
- Database connectivity
- Table existence
- Port availability

**Usage:**
```bash
./scripts/check_docker_env.sh
```

### 3. `scripts/start_api.sh`

Standalone API startup script with automatic configuration.

**Features:**
- Automatic PostgreSQL port detection
- DATABASE_URL configuration
- Virtual environment activation
- Container status verification

**Usage:**
```bash
./scripts/start_api.sh
```

### 4. `scripts/init_postgres_all_models.py`

Database initialization script that creates all required tables.

**Tables Created:**
1. users
2. audit_logs
3. company_profiles
4. procurement_tenders
5. procurement_documents
6. bid_responses
7. capability_matches
8. compliance_checks
9. extracted_requirements
10. processing_events

## Environment Configuration

### Database Connection

The system automatically configures the DATABASE_URL:
```bash
postgresql+asyncpg://scorpius:scorpiusdev@localhost:5434/scorpius_dev
```

### Export File

The initialization creates `.env.export` for easy sourcing:
```bash
source .env.export
```

### Docker Compose

The `docker-compose.local.yml` is dynamically generated with the correct port configuration.

## Default Credentials

### Database
- **User:** scorpius
- **Password:** scorpiusdev
- **Database:** scorpius_dev
- **Port:** 5434 (or next available)

### Test Users

#### Admin User
- **Email:** admin@scorpius.fr
- **Password:** Admin123!
- **Role:** admin

#### Test User
- **Email:** test@scorpius.fr
- **Password:** Xw9!Kp2@Qm7
- **Role:** bid_manager

## Port Management

The system automatically handles port conflicts:

1. **Default Port:** 5434
2. **Fallback Ports:** 5435, 5436, 5437, 5438
3. **Detection:** Checks if ports are in use
4. **Configuration:** Updates all files automatically

## Troubleshooting

### Common Issues and Solutions

#### 1. Port Already in Use
**Solution:** The script automatically finds the next available port.

#### 2. SQLite Instead of PostgreSQL
**Solution:** The script exports DATABASE_URL automatically.

#### 3. Authentication Failures
**Solution:** Test users are created with compliant passwords.

#### 4. Docker Compose Version Warning
**Solution:** The script generates modern compose files without version attribute.

### Manual Verification

```bash
# Check container status
docker ps

# Verify database connection
docker exec scorpius-postgres-local psql -U scorpius -d scorpius_dev -c "\\dt"

# Test API health
curl http://localhost:8000/api/v1/health | jq

# View API logs
docker logs -f $(docker ps -q --filter name=scorpius-api)
```

## API Endpoints

Once initialized, the following endpoints are available:

### Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Health Check
- **GET** `/api/v1/health` - System health status

### Authentication
- **POST** `/api/v1/auth/register` - User registration
- **POST** `/api/v1/auth/login` - User login
- **POST** `/api/v1/auth/refresh` - Token refresh
- **GET** `/api/v1/auth/me` - Current user profile

## Development Workflow

### Standard Development Setup

```bash
# 1. Clean initialization
./scripts/init_docker_env.sh --clean

# 2. Source DATABASE_URL
source .env.export

# 3. Start API manually (if not using --start-api)
./scripts/start_api.sh
```

### Reset Environment

```bash
# Complete reset and restart
./scripts/init_docker_env.sh --clean --start-api
```

### Stop Services

```bash
# Stop all Docker services
docker-compose -f docker-compose.local.yml down

# Stop with volume removal
docker-compose -f docker-compose.local.yml down -v
```

## Testing

### Run Phase 3 Tender Tests
```bash
source venv_py311/bin/activate
python test_phase3_endpoints.py
```

### Create Test Data
```bash
# Register test user
python /tmp/register_test_user.py

# Run integration tests
pytest tests/integration -v
```

## Best Practices

1. **Always use the init script** for consistent setup
2. **Use --clean flag** when encountering issues
3. **Check logs** if services fail to start
4. **Source .env.export** before manual API operations
5. **Verify health endpoint** after initialization

## Script Exit Codes

- `0` - Success
- `1` - General error
- `2` - Prerequisites not met
- `3` - Docker services failed
- `4` - Database initialization failed

## Future Improvements

1. ✅ Automatic port detection
2. ✅ DATABASE_URL export
3. ✅ Integrated API startup
4. ✅ Test user creation
5. ⚠️ Tender endpoints implementation (in progress)
6. 🔄 CI/CD integration (planned)
7. 🔄 Production deployment automation (planned)

## Summary

The Docker initialization system provides:
- **One-command setup** for complete environment
- **Automatic error recovery** and port management
- **Idempotent operations** safe for repeated runs
- **Comprehensive validation** at each step
- **Clear feedback** with colored output
- **Robust error handling** with meaningful messages

This automation eliminates all manual steps and common initialization problems, ensuring a consistent development environment every time.