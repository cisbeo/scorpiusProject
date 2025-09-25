#!/bin/bash

# Script de vérification de l'environnement Docker
# Scorpius Project - Vérifie l'état et la santé du système
# Usage: ./scripts/check_docker_env.sh [--verbose]

set -e

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
VERBOSE=false

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Parse arguments
if [[ "$1" == "--verbose" ]]; then
    VERBOSE=true
fi

# Fonctions d'affichage
print_header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
}

print_check() {
    local status=$1
    local message=$2
    if [[ "$status" == "ok" ]]; then
        echo -e "  ${GREEN}✅${NC} $message"
    elif [[ "$status" == "warning" ]]; then
        echo -e "  ${YELLOW}⚠️${NC} $message"
    else
        echo -e "  ${RED}❌${NC} $message"
    fi
}

print_info() {
    echo -e "  ${BLUE}ℹ️${NC} $1"
}

# Récupérer les informations depuis .env
get_env_value() {
    local key=$1
    local env_file="$PROJECT_ROOT/.env"
    if [ -f "$env_file" ]; then
        grep "^$key=" "$env_file" | cut -d'=' -f2 | tr -d '"' | tr -d "'"
    fi
}

# Vérification Docker
check_docker() {
    print_header "DOCKER & DOCKER COMPOSE"

    # Docker installé
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
        print_check "ok" "Docker installé (version $DOCKER_VERSION)"
    else
        print_check "error" "Docker non installé"
        return 1
    fi

    # Docker démarré
    if docker info &> /dev/null; then
        print_check "ok" "Docker daemon en cours d'exécution"
    else
        print_check "error" "Docker daemon non démarré"
        return 1
    fi

    # Docker Compose
    if command -v docker-compose &> /dev/null; then
        DC_VERSION=$(docker-compose --version | cut -d' ' -f3 | tr -d ',')
        print_check "ok" "Docker Compose installé (version $DC_VERSION)"
    elif docker compose version &> /dev/null; then
        print_check "ok" "Docker Compose (plugin) disponible"
    else
        print_check "warning" "Docker Compose non trouvé"
    fi

    return 0
}

# Vérification des conteneurs
check_containers() {
    print_header "CONTENEURS DOCKER"

    local postgres_running=false
    local redis_running=false

    # PostgreSQL
    if docker ps | grep -q scorpius-postgres-local; then
        postgres_running=true
        POSTGRES_STATUS=$(docker inspect scorpius-postgres-local --format='{{.State.Status}}')
        POSTGRES_HEALTH=$(docker inspect scorpius-postgres-local --format='{{.State.Health.Status}}' 2>/dev/null || echo "n/a")

        if [[ "$POSTGRES_STATUS" == "running" ]]; then
            if [[ "$POSTGRES_HEALTH" == "healthy" ]]; then
                print_check "ok" "PostgreSQL: en cours d'exécution (healthy)"
            else
                print_check "warning" "PostgreSQL: en cours d'exécution (health: $POSTGRES_HEALTH)"
            fi
        else
            print_check "error" "PostgreSQL: état $POSTGRES_STATUS"
        fi

        # Détails si verbose
        if [ "$VERBOSE" = true ]; then
            POSTGRES_PORT=$(docker port scorpius-postgres-local 5432 | cut -d':' -f2)
            print_info "Port mappé: $POSTGRES_PORT"
        fi
    else
        print_check "error" "PostgreSQL: conteneur non trouvé"
    fi

    # Redis
    if docker ps | grep -q scorpius-redis-local; then
        redis_running=true
        REDIS_STATUS=$(docker inspect scorpius-redis-local --format='{{.State.Status}}')

        if [[ "$REDIS_STATUS" == "running" ]]; then
            print_check "ok" "Redis: en cours d'exécution"
        else
            print_check "error" "Redis: état $REDIS_STATUS"
        fi

        # Détails si verbose
        if [ "$VERBOSE" = true ]; then
            REDIS_PORT=$(docker port scorpius-redis-local 6379 | cut -d':' -f2)
            print_info "Port mappé: $REDIS_PORT"
        fi
    else
        print_check "error" "Redis: conteneur non trouvé"
    fi

    # Volumes
    if [ "$VERBOSE" = true ]; then
        echo ""
        print_info "Volumes Docker:"
        docker volume ls | grep scorpius | while read -r line; do
            echo "    $line"
        done
    fi
}

# Vérification de la configuration
check_configuration() {
    print_header "CONFIGURATION"

    # Fichier .env
    if [ -f "$PROJECT_ROOT/.env" ]; then
        print_check "ok" "Fichier .env présent"

        # Vérifier DATABASE_URL
        DATABASE_URL=$(get_env_value "DATABASE_URL")
        if [[ -n "$DATABASE_URL" ]]; then
            if [[ "$DATABASE_URL" == *"postgresql"* ]]; then
                # Extraire le port
                PORT=$(echo "$DATABASE_URL" | sed -n 's/.*localhost:\([0-9]*\).*/\1/p')
                print_check "ok" "DATABASE_URL configurée (PostgreSQL sur port $PORT)"
            elif [[ "$DATABASE_URL" == *"sqlite"* ]]; then
                print_check "warning" "DATABASE_URL pointe vers SQLite"
            else
                print_check "warning" "DATABASE_URL format non reconnu"
            fi
        else
            print_check "error" "DATABASE_URL non définie"
        fi

        # Vérifier REDIS_URL
        REDIS_URL=$(get_env_value "REDIS_URL")
        if [[ -n "$REDIS_URL" ]]; then
            print_check "ok" "REDIS_URL configurée"
        else
            print_check "warning" "REDIS_URL non définie"
        fi
    else
        print_check "error" "Fichier .env manquant"
    fi

    # docker-compose.local.yml
    if [ -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
        print_check "ok" "Fichier docker-compose.local.yml présent"
    else
        print_check "error" "Fichier docker-compose.local.yml manquant"
    fi

    # Environnement Python
    if [ -d "$PROJECT_ROOT/venv_py311" ]; then
        print_check "ok" "Environnement virtuel Python présent (venv_py311)"
    elif [ -d "$PROJECT_ROOT/venv" ]; then
        print_check "warning" "Environnement virtuel présent (venv) - venv_py311 recommandé"
    else
        print_check "error" "Environnement virtuel Python non trouvé"
    fi
}

# Vérification de la base de données
check_database() {
    print_header "BASE DE DONNÉES POSTGRESQL"

    # Récupérer les infos de connexion
    DATABASE_URL=$(get_env_value "DATABASE_URL")
    if [[ -z "$DATABASE_URL" ]]; then
        print_check "error" "DATABASE_URL non configurée"
        return 1
    fi

    # Parser l'URL
    if [[ "$DATABASE_URL" =~ postgresql.*://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
        DB_USER="${BASH_REMATCH[1]}"
        DB_PASS="${BASH_REMATCH[2]}"
        DB_HOST="${BASH_REMATCH[3]}"
        DB_PORT="${BASH_REMATCH[4]}"
        DB_NAME="${BASH_REMATCH[5]}"
    else
        print_check "error" "Format DATABASE_URL invalide"
        return 1
    fi

    # Test de connexion
    export PGPASSWORD="$DB_PASS"

    # Test via psql local si disponible
    if command -v psql &> /dev/null; then
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
            print_check "ok" "Connexion PostgreSQL réussie (psql local)"
        else
            print_check "error" "Impossible de se connecter à PostgreSQL"
        fi
    else
        # Test via Docker
        if docker exec scorpius-postgres-local psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
            print_check "ok" "Connexion PostgreSQL réussie (via Docker)"
        else
            print_check "error" "Impossible de se connecter à PostgreSQL"
            return 1
        fi
    fi

    # Compter les tables
    TABLE_COUNT=$(docker exec scorpius-postgres-local psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

    if [[ -n "$TABLE_COUNT" && "$TABLE_COUNT" -gt 0 ]]; then
        print_check "ok" "$TABLE_COUNT tables trouvées dans la base de données"

        # Lister les tables si verbose
        if [ "$VERBOSE" = true ]; then
            echo ""
            print_info "Tables existantes:"
            docker exec scorpius-postgres-local psql -U "$DB_USER" -d "$DB_NAME" -c "\dt" 2>/dev/null | grep "public\." | while read -r line; do
                echo "    $line"
            done
        fi

        # Vérifier les tables essentielles
        ESSENTIAL_TABLES=("users" "procurement_documents" "procurement_tenders" "company_profiles")
        for table in "${ESSENTIAL_TABLES[@]}"; do
            TABLE_EXISTS=$(docker exec scorpius-postgres-local psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '$table');" 2>/dev/null | tr -d ' ')
            if [[ "$TABLE_EXISTS" == "t" ]]; then
                print_check "ok" "Table '$table' présente"
            else
                print_check "warning" "Table '$table' manquante"
            fi
        done

    else
        print_check "warning" "Aucune table trouvée dans la base de données"
        print_info "Exécutez './scripts/init_docker_env.sh' pour initialiser"
    fi
}

# Vérification des connexions
check_connections() {
    print_header "TEST DES CONNEXIONS"

    # Redis ping
    if docker exec scorpius-redis-local redis-cli ping &> /dev/null; then
        print_check "ok" "Redis répond au ping"
    else
        print_check "error" "Redis ne répond pas"
    fi

    # Test API si en cours d'exécution
    if curl -s http://localhost:8000/health &> /dev/null; then
        print_check "ok" "API accessible sur http://localhost:8000"
    else
        print_check "warning" "API non accessible (pas démarrée ?)"
        print_info "Démarrer avec: source venv_py311/bin/activate && uvicorn src.main:app --reload"
    fi
}

# Résumé et recommandations
print_summary() {
    print_header "RÉSUMÉ ET RECOMMANDATIONS"

    local all_good=true
    local recommendations=()

    # Analyser l'état
    if ! docker ps | grep -q scorpius-postgres-local; then
        all_good=false
        recommendations+=("Démarrer PostgreSQL: docker-compose -f docker-compose.local.yml up -d postgres")
    fi

    if ! docker ps | grep -q scorpius-redis-local; then
        all_good=false
        recommendations+=("Démarrer Redis: docker-compose -f docker-compose.local.yml up -d redis")
    fi

    DATABASE_URL=$(get_env_value "DATABASE_URL")
    if [[ "$DATABASE_URL" == *"sqlite"* ]]; then
        all_good=false
        recommendations+=("Mettre à jour DATABASE_URL pour PostgreSQL dans .env")
    fi

    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        all_good=false
        recommendations+=("Créer le fichier .env: cp .env.example .env")
    fi

    if [ ! -d "$PROJECT_ROOT/venv_py311" ] && [ ! -d "$PROJECT_ROOT/venv" ]; then
        all_good=false
        recommendations+=("Créer l'environnement Python: python3.11 -m venv venv_py311")
    fi

    # Afficher le statut
    if [ "$all_good" = true ]; then
        echo -e "${GREEN}"
        echo "  ✅ Environnement opérationnel !"
        echo -e "${NC}"
        echo ""
        print_info "Commandes utiles:"
        echo "    • Démarrer l'API: source venv_py311/bin/activate && uvicorn src.main:app --reload"
        echo "    • Voir les logs: docker-compose -f docker-compose.local.yml logs -f"
        echo "    • Documentation: http://localhost:8000/docs"
    else
        echo -e "${YELLOW}"
        echo "  ⚠️ Attention: Des problèmes ont été détectés"
        echo -e "${NC}"
        echo ""
        print_info "Recommandations:"
        for rec in "${recommendations[@]}"; do
            echo "    • $rec"
        done
        echo ""
        print_info "Pour une réinitialisation complète:"
        echo "    ./scripts/init_docker_env.sh --clean"
    fi
}

# Programme principal
main() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     VÉRIFICATION ENVIRONNEMENT SCORPIUS PROJECT    ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════╝${NC}"

    cd "$PROJECT_ROOT"

    # Exécuter les vérifications
    check_docker
    check_containers
    check_configuration
    check_database
    check_connections
    print_summary

    echo ""
}

# Exécution
main