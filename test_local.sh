#!/bin/bash

# Script de test local rapide - Scorpius Project
# Usage: ./test_local.sh [setup|start|test|clean]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Setup local environment
setup_local() {
    log "Configuration de l'environnement local..."

    # Créer les dossiers nécessaires
    mkdir -p uploads temp logs

    # Vérifier Python et pip
    if ! command -v python3 &> /dev/null; then
        error "Python 3 n'est pas installé"
        exit 1
    fi

    if ! command -v pip &> /dev/null; then
        error "pip n'est pas installé"
        exit 1
    fi

    # Installer les dépendances
    log "Installation des dépendances..."
    pip install -r requirements.txt
    pip install aiosqlite  # SQLite async pour tests locaux

    # Initialiser la base de données SQLite
    log "Initialisation de la base de données SQLite..."
    python3 -c "
import asyncio
import os
import sys
sys.path.append('.')

os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_scorpius.db'

from src.db.session import async_engine
from src.db.base import Base

async def init_db():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print('✅ Base de données SQLite initialisée avec succès')
    except Exception as e:
        print(f'❌ Erreur lors de l\'initialisation: {e}')
        exit(1)

asyncio.run(init_db())
"

    log "Environnement local configuré avec succès !"
    info "Vous pouvez maintenant lancer: ./test_local.sh start"
}

# Start the API
start_api() {
    log "Démarrage de l'API Scorpius en mode développement..."

    # Vérifier que la base existe
    if [[ ! -f "test_scorpius.db" ]]; then
        warning "Base de données non trouvée, initialisation..."
        setup_local
    fi

    # Démarrer l'API avec rechargement automatique
    info "API disponible sur: http://localhost:8000"
    info "Documentation: http://localhost:8000/docs"
    info "Santé: http://localhost:8000/health"
    echo

    uvicorn main:app --reload --host 0.0.0.0 --port 8000 --env-file .env.local
}

# Test the API
test_api() {
    log "Tests de l'API Scorpius..."

    # Attendre que l'API soit disponible
    info "Vérification que l'API est démarrée..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            error "L'API n'est pas accessible sur http://localhost:8000"
            exit 1
        fi
        sleep 1
    done

    log "✅ API accessible"

    # Test de santé
    echo
    info "Test de santé..."
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
    echo "Réponse santé: $HEALTH_RESPONSE"

    # Test d'enregistrement
    echo
    info "Test d'enregistrement utilisateur..."
    REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test@example.com",
            "password": "TestPass1!",
            "full_name": "Utilisateur Test",
            "role": "bid_manager"
        }')
    echo "Réponse enregistrement: $REGISTER_RESPONSE"

    # Test de connexion
    echo
    info "Test de connexion..."
    LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
        -H "Content-Type: application/json" \
        -d '{
            "email": "test@example.com",
            "password": "TestPass1!"
        }')
    echo "Réponse connexion: $LOGIN_RESPONSE"

    # Extraire le token
    TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data['tokens']['access_token'])
except:
    print('')
")

    if [[ -n "$TOKEN" ]]; then
        log "✅ Token obtenu avec succès"

        # Test GET /me endpoint (authentication test)
        echo
        info "Test endpoint GET /me (authentification)..."
        ME_RESPONSE=$(curl -s -X GET http://localhost:8000/api/v1/auth/me \
            -H "Authorization: Bearer $TOKEN")
        echo "Réponse GET /me: $ME_RESPONSE"

        if echo "$ME_RESPONSE" | grep -q '"id"'; then
            log "✅ GET /me fonctionne - authentification OK"
        else
            warning "❌ GET /me échoue - problème d'authentification middleware"
            echo "Token utilisé: ${TOKEN:0:50}..."
        fi

        # Test de création de profil entreprise
        echo
        info "Test de création profil entreprise..."
        COMPANY_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/company-profile \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{
                "company_name": "Ma Société Test SARL",
                "siret": "12345678901234",
                "description": "Société de test pour Scorpius",
                "capabilities_json": [
                    {"name": "Développement Web", "keywords": ["Python", "FastAPI"]},
                    {"name": "Consulting IT", "keywords": ["Architecture", "Cloud"]}
                ],
                "team_size": 10,
                "annual_revenue": 500000.0
            }')
        echo "Réponse profil entreprise: $COMPANY_RESPONSE"

        # Test d'upload de document (PDF simple)
        echo
        info "Test d'upload de document..."

        # Créer un PDF minimal pour test
        cat > test.pdf << 'EOF'
%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000010 00000 n
0000000079 00000 n
0000000173 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
301
%%EOF
EOF

        UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/documents \
            -H "Authorization: Bearer $TOKEN" \
            -F "file=@test.pdf" \
            -F "title=Document Test Local")
        echo "Réponse upload: $UPLOAD_RESPONSE"

        # Nettoyer
        rm -f test.pdf

        log "✅ Tests fonctionnels terminés avec succès"
    else
        error "Impossible d'obtenir le token de connexion"
    fi

    echo
    log "🎉 Tests de l'API Scorpius terminés !"
    info "Vous pouvez maintenant tester manuellement sur:"
    info "- Documentation interactive: http://localhost:8000/docs"
    info "- Santé: http://localhost:8000/health"
    info "- API Root: http://localhost:8000/"
}

# Clean local environment
clean_local() {
    log "Nettoyage de l'environnement local..."

    # Supprimer les fichiers temporaires
    rm -f test_scorpius.db test.pdf
    rm -rf uploads/* temp/* logs/* __pycache__ .pytest_cache

    log "Environnement nettoyé"
}

# Main script logic
case "${1:-}" in
    setup)
        setup_local
        ;;
    start)
        start_api
        ;;
    test)
        test_api
        ;;
    clean)
        clean_local
        ;;
    *)
        echo "Script de test local - Scorpius Project"
        echo
        echo "Usage: $0 {setup|start|test|clean}"
        echo
        echo "Commandes:"
        echo "  setup  - Configure l'environnement local (dépendances + base SQLite)"
        echo "  start  - Démarre l'API en mode développement avec rechargement"
        echo "  test   - Lance les tests fonctionnels de l'API"
        echo "  clean  - Nettoie l'environnement local"
        echo
        echo "Workflow recommandé:"
        echo "  1. ./test_local.sh setup    # Une seule fois"
        echo "  2. ./test_local.sh start    # Démarre l'API"
        echo "  3. ./test_local.sh test     # Dans un autre terminal"
        echo
        echo "Ensuite testez manuellement sur http://localhost:8000/docs"
        ;;
esac