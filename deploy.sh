#!/bin/bash

# Scorpius Project - Production Deployment Script
# Usage: ./deploy.sh [init|start|stop|restart|logs|backup|restore]

set -e

# Configuration
PROJECT_DIR="/opt/scorpius"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Check if user is in docker group
    if ! groups | grep -q docker; then
        error "Current user is not in the docker group. Run: sudo usermod -aG docker $USER"
        exit 1
    fi

    log "Prerequisites check passed"
}

# Generate secrets
generate_secrets() {
    log "Generating secrets..."

    if [[ ! -f "$ENV_FILE" ]]; then
        cp .env.prod.example $ENV_FILE

        # Generate secrets
        JWT_SECRET=$(openssl rand -hex 32)
        APP_SECRET=$(openssl rand -hex 32)
        DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
        REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

        # Replace placeholders in .env.prod
        sed -i "s/your_jwt_secret_key_here/$JWT_SECRET/g" $ENV_FILE
        sed -i "s/your_app_secret_key_here/$APP_SECRET/g" $ENV_FILE
        sed -i "s/your_secure_db_password_here/$DB_PASSWORD/g" $ENV_FILE
        sed -i "s/your_secure_redis_password_here/$REDIS_PASSWORD/g" $ENV_FILE

        warning "Secrets generated in $ENV_FILE"
        warning "Please review and update domain names and other settings before deployment"
    else
        info "Environment file already exists, skipping secret generation"
    fi
}

# Setup directories
setup_directories() {
    log "Setting up directories..."

    mkdir -p uploads logs temp backups nginx/ssl nginx/logs
    chmod 755 uploads logs temp backups
    chmod 700 nginx/ssl

    log "Directories created successfully"
}

# Initialize SSL certificates (placeholder)
setup_ssl() {
    log "Setting up SSL certificates..."

    if [[ ! -f "nginx/ssl/cert.pem" ]]; then
        warning "SSL certificates not found. Creating self-signed certificates for testing..."
        warning "For production, replace with proper certificates from Let's Encrypt or your CA"

        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/C=FR/ST=France/L=Paris/O=Scorpius/CN=localhost"

        chmod 600 nginx/ssl/key.pem
        chmod 644 nginx/ssl/cert.pem
    else
        info "SSL certificates already exist"
    fi
}

# Initialize project
init_project() {
    log "Initializing Scorpius project for production deployment..."

    check_prerequisites
    generate_secrets
    setup_directories
    setup_ssl

    log "Project initialization completed"
    warning "Please review $ENV_FILE and update the domain name before starting"
}

# Build and start services
start_services() {
    log "Starting Scorpius services..."

    # Check if .env.prod exists
    if [[ ! -f "$ENV_FILE" ]]; then
        error "Environment file $ENV_FILE not found. Run './deploy.sh init' first."
        exit 1
    fi

    # Load environment variables
    set -o allexport
    source $ENV_FILE
    set +o allexport

    # Build and start services
    docker-compose -f $COMPOSE_FILE build --no-cache
    docker-compose -f $COMPOSE_FILE up -d

    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 30

    # Check service health
    check_health

    log "Services started successfully"
}

# Stop services
stop_services() {
    log "Stopping Scorpius services..."
    docker-compose -f $COMPOSE_FILE down
    log "Services stopped"
}

# Restart services
restart_services() {
    log "Restarting Scorpius services..."
    stop_services
    start_services
}

# Check service health
check_health() {
    log "Checking service health..."

    # Check database
    if docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U scorpius -d scorpius_prod; then
        info "✓ Database is healthy"
    else
        error "✗ Database is not healthy"
    fi

    # Check Redis
    if docker-compose -f $COMPOSE_FILE exec -T redis redis-cli ping | grep -q PONG; then
        info "✓ Redis is healthy"
    else
        error "✗ Redis is not healthy"
    fi

    # Check API
    sleep 5
    if curl -sf http://localhost:8000/health > /dev/null; then
        info "✓ API is healthy"
    else
        error "✗ API is not healthy"
    fi
}

# Show logs
show_logs() {
    docker-compose -f $COMPOSE_FILE logs -f "${2:-}"
}

# Backup database
backup_database() {
    log "Creating database backup..."

    BACKUP_FILE="backups/backup_$(date +%Y%m%d_%H%M%S).sql"

    docker-compose -f $COMPOSE_FILE exec -T postgres pg_dump -U scorpius scorpius_prod > $BACKUP_FILE

    if [[ -f "$BACKUP_FILE" ]]; then
        log "Database backup created: $BACKUP_FILE"

        # Keep only last 7 backups
        find backups/ -name "backup_*.sql" -mtime +7 -delete
    else
        error "Failed to create database backup"
        exit 1
    fi
}

# Restore database
restore_database() {
    if [[ -z "$2" ]]; then
        error "Usage: ./deploy.sh restore <backup_file>"
        exit 1
    fi

    BACKUP_FILE="$2"

    if [[ ! -f "$BACKUP_FILE" ]]; then
        error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    warning "This will restore database from: $BACKUP_FILE"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Restore cancelled"
        exit 0
    fi

    log "Restoring database from backup..."

    # Stop API to prevent connections
    docker-compose -f $COMPOSE_FILE stop api

    # Restore database
    docker-compose -f $COMPOSE_FILE exec -T postgres psql -U scorpius -d scorpius_prod < $BACKUP_FILE

    # Start API
    docker-compose -f $COMPOSE_FILE start api

    log "Database restored successfully"
}

# Initialize database
init_database() {
    log "Initializing database..."

    # Wait for database to be ready
    sleep 10

    # Check if tables already exist
    TABLES=$(docker-compose -f $COMPOSE_FILE exec -T postgres psql -U scorpius -d scorpius_prod -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")

    if [ "$TABLES" -gt 0 ]; then
        warning "Database already has tables. Use 'reinit-db' to force recreation."
        return
    fi

    # Create tables using the init_db.py script
    docker-compose -f $COMPOSE_FILE exec -T api python /app/scripts/init_db.py

    log "Database initialized successfully"
}

# Reinitialize database (drops and recreates all tables)
reinit_database() {
    log "Re-initializing database (this will DROP all existing tables)..."

    read -p "⚠️  WARNING: This will DELETE all data. Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Operation cancelled"
        exit 0
    fi

    # Drop all tables
    docker-compose -f $COMPOSE_FILE exec -T postgres psql -U scorpius -d scorpius_prod -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

    # Create tables using the init_db.py script
    docker-compose -f $COMPOSE_FILE exec -T api python /app/scripts/init_db.py

    log "Database re-initialized successfully"
}

# Update application
update_application() {
    log "Updating Scorpius application..."

    # Create backup before update
    backup_database

    # Pull latest changes
    git pull origin main

    # Rebuild and restart
    restart_services

    log "Application updated successfully"
}

# Show system status
show_status() {
    echo "=== Scorpius System Status ==="
    echo

    echo "Services:"
    docker-compose -f $COMPOSE_FILE ps
    echo

    echo "Health Checks:"
    check_health
    echo

    echo "Disk Usage:"
    df -h . | tail -1
    echo

    echo "Memory Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
}

# Main script logic
case "${1:-}" in
    init)
        init_project
        ;;
    start)
        start_services
        init_database
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs "$@"
        ;;
    backup)
        backup_database
        ;;
    restore)
        restore_database "$@"
        ;;
    update)
        update_application
        ;;
    status)
        show_status
        ;;
    health)
        check_health
        ;;
    init-db)
        init_database
        ;;
    reinit-db)
        reinit_database
        ;;
    *)
        echo "Scorpius Project - Production Deployment Script"
        echo
        echo "Usage: $0 {init|start|stop|restart|logs|backup|restore|update|status|health|init-db|reinit-db}"
        echo
        echo "Commands:"
        echo "  init       - Initialize project (generate secrets, setup directories)"
        echo "  start      - Build and start all services"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  logs       - Show service logs (logs [service])"
        echo "  backup     - Create database backup"
        echo "  restore    - Restore database from backup (restore <file>)"
        echo "  update     - Update application from git and restart"
        echo "  init-db    - Initialize database tables (safe, skips if tables exist)"
        echo "  reinit-db  - Re-initialize database (WARNING: drops all tables)"
        echo "  status   - Show system status"
        echo "  health   - Check service health"
        echo
        exit 1
        ;;
esac