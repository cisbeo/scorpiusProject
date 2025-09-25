#!/bin/bash

# Script de démarrage rapide de l'API avec PostgreSQL
# Scorpius Project
# Usage: ./scripts/start_api.sh [--port PORT_API]

set -e

# Configuration par défaut
API_PORT=8000
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Parse des arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            API_PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--port PORT_API]"
            echo ""
            echo "Options:"
            echo "  --port PORT  Port pour l'API (défaut: 8000)"
            echo "  --help       Affiche cette aide"
            exit 0
            ;;
        *)
            echo -e "${RED}Option inconnue: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🚀 Démarrage de l'API Scorpius${NC}"
echo "================================"

# Aller au répertoire du projet
cd "$PROJECT_ROOT"

# Vérifier si Docker est en cours d'exécution
if ! docker ps | grep -q scorpius-postgres-local; then
    echo -e "${YELLOW}⚠️ PostgreSQL n'est pas démarré${NC}"
    echo "Lancement de l'environnement Docker..."

    if [ -f "./scripts/init_docker_env.sh" ]; then
        ./scripts/init_docker_env.sh
    else
        echo -e "${RED}❌ Script init_docker_env.sh non trouvé${NC}"
        exit 1
    fi
fi

# Détecter le port PostgreSQL utilisé
PG_PORT=$(docker port scorpius-postgres-local 5432 2>/dev/null | cut -d: -f2)
if [ -z "$PG_PORT" ]; then
    PG_PORT=5434  # Port par défaut
fi

echo -e "${BLUE}[INFO]${NC} PostgreSQL détecté sur le port: $PG_PORT"

# Configurer DATABASE_URL
export DATABASE_URL="postgresql+asyncpg://scorpius:scorpiusdev@localhost:${PG_PORT}/scorpius_dev"
echo -e "${GREEN}✅${NC} DATABASE_URL configuré: $DATABASE_URL"

# Vérifier si le venv existe
if [ ! -d "venv_py311" ]; then
    echo -e "${RED}❌ Environnement virtuel Python non trouvé${NC}"
    echo "Créez-le avec: python3.11 -m venv venv_py311"
    exit 1
fi

# Activer l'environnement virtuel
echo -e "${BLUE}[INFO]${NC} Activation de l'environnement virtuel..."
source venv_py311/bin/activate

# Vérifier les dépendances
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️ Installation des dépendances...${NC}"
    pip install -q -r requirements.txt
fi

# Lancer l'API
echo -e "${GREEN}✅${NC} Démarrage de l'API sur le port $API_PORT"
echo ""
echo -e "${BLUE}📚 Documentation disponible sur:${NC} http://localhost:${API_PORT}/docs"
echo -e "${BLUE}📊 Health check:${NC} http://localhost:${API_PORT}/api/v1/health"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter l'API"
echo "================================"

# Démarrer uvicorn
uvicorn src.api.v1.app:app --reload --port ${API_PORT} --host 0.0.0.0