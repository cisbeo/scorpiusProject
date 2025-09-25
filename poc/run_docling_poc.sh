#!/bin/bash

# Script pour lancer le POC Docling avec Docker
# Usage: ./run_docling_poc.sh [build|start|stop|test|logs]

set -e

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOCKER_DIR="docker/docling-poc"
POC_DIR="poc"
API_URL="http://localhost:8001"

# Fonction pour afficher les messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Fonction pour construire l'image Docker
build_docker() {
    log_info "Construction de l'image Docker Docling..."

    cd $DOCKER_DIR

    # Créer les dossiers nécessaires
    mkdir -p output logs

    # Construire l'image
    docker-compose build

    log_success "Image Docker construite avec succès !"
}

# Fonction pour démarrer les services
start_services() {
    log_info "Démarrage des services Docling..."

    cd $DOCKER_DIR

    # Démarrer les conteneurs
    docker-compose up -d

    # Attendre que l'API soit prête
    log_info "Attente du démarrage de l'API..."
    sleep 5

    # Vérifier la santé
    if curl -f ${API_URL}/health > /dev/null 2>&1; then
        log_success "API Docling démarrée avec succès !"
        log_info "🌐 Interface de démo: ${API_URL}/demo"
        log_info "📚 Documentation API: ${API_URL}/docs"
    else
        log_error "L'API n'a pas démarré correctement"
        docker-compose logs docling-poc
        exit 1
    fi
}

# Fonction pour arrêter les services
stop_services() {
    log_info "Arrêt des services Docling..."

    cd $DOCKER_DIR
    docker-compose down

    log_success "Services arrêtés"
}

# Fonction pour afficher les logs
show_logs() {
    cd $DOCKER_DIR
    docker-compose logs -f docling-poc
}

# Fonction pour tester l'extraction
test_extraction() {
    log_info "Test d'extraction sur CCTP problématique..."

    # Test de l'endpoint health
    log_info "Vérification de la santé du service..."
    curl -s ${API_URL}/health | python -m json.tool

    # Test avec CCTP problématique
    log_info "Test avec CCTP simulé..."
    response=$(curl -s ${API_URL}/test/cctp)

    if [ $? -eq 0 ]; then
        echo "$response" | python -m json.tool

        # Analyser les résultats
        has_docling_problems=$(echo "$response" | python -c "import sys, json; data = json.load(sys.stdin); print(data['docling']['has_problems'])")
        has_traditional_problems=$(echo "$response" | python -c "import sys, json; data = json.load(sys.stdin); print(data['traditional']['has_problems'])")

        echo ""
        log_info "=== RÉSUMÉ DU TEST ==="

        if [ "$has_docling_problems" == "False" ] && [ "$has_traditional_problems" == "True" ]; then
            log_success "✅ Docling résout les problèmes d'espacement !"
        else
            log_warning "⚠️ Docling n'a pas résolu tous les problèmes"
        fi

        # Afficher les améliorations
        improvements=$(echo "$response" | python -c "
import sys, json
data = json.load(sys.stdin)
for key, value in data.get('improvements', {}).items():
    print(f'  • {key}: {value}')
")

        if [ ! -z "$improvements" ]; then
            log_info "Améliorations Docling:"
            echo "$improvements"
        fi

    else
        log_error "Échec du test"
    fi
}

# Fonction pour créer un fichier PDF de test
create_test_pdf() {
    log_info "Création d'un PDF de test avec problèmes Word 2013..."

    # Script Python pour créer le PDF
    python3 << 'EOF'
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

pdf_path = "test_cctp_problematic.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)

# Titre avec espaces problématiques (simule Word 2013)
c.setFont("Helvetica-Bold", 16)
c.drawString(100, 750, "ACCOMPAGNEMENT AU PR OGRAMME")
c.drawString(100, 730, "DE TRANSFORMATION DI GITALE HEC PARIS")

c.setFont("Helvetica-Bold", 14)
c.drawString(100, 690, "CAHIER DES CLAUSES TECHNIQUES (CCTP)")

c.setFont("Helvetica", 12)
c.drawString(100, 650, "1. Objet du marché")
c.drawString(100, 620, "La présente consultation porte sur la fourniture de prestations de")
c.drawString(100, 600, "management de pr ogramme, et gestion de projets Agiles,")
c.drawString(100, 580, "accompagnement à la démarche d'in novation par la méthode")
c.drawString(100, 560, "Design Thinking.")

c.drawString(100, 520, "La partie A comprend les prestations suivantes :")
c.drawString(120, 500, "- Program Management Office (~1 ETP sur 6 mois)")
c.drawString(120, 480, "- Organisation et an imation d'ateliers Design Thinking")
c.drawString(120, 460, "- Conseil en architecture d'en treprise")

c.showPage()
c.save()

print(f"✅ PDF de test créé: {pdf_path}")
EOF

    log_success "PDF de test créé: test_cctp_problematic.pdf"
}

# Menu principal
case "${1:-help}" in
    build)
        build_docker
        ;;

    start)
        build_docker
        start_services
        ;;

    stop)
        stop_services
        ;;

    restart)
        stop_services
        start_services
        ;;

    test)
        test_extraction
        ;;

    logs)
        show_logs
        ;;

    create-test-pdf)
        create_test_pdf
        ;;

    demo)
        log_info "Ouverture de l'interface de démo..."
        open ${API_URL}/demo || xdg-open ${API_URL}/demo
        ;;

    *)
        echo "Usage: $0 {build|start|stop|restart|test|logs|create-test-pdf|demo}"
        echo ""
        echo "Commands:"
        echo "  build           - Construire l'image Docker"
        echo "  start           - Démarrer les services (build + up)"
        echo "  stop            - Arrêter les services"
        echo "  restart         - Redémarrer les services"
        echo "  test            - Tester l'extraction sur CCTP"
        echo "  logs            - Afficher les logs"
        echo "  create-test-pdf - Créer un PDF de test problématique"
        echo "  demo            - Ouvrir l'interface web de démo"
        echo ""
        echo "Exemple:"
        echo "  $0 start   # Démarre le POC"
        echo "  $0 test    # Lance les tests"
        echo "  $0 demo    # Ouvre l'interface web"
        exit 1
        ;;
esac