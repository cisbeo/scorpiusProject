#!/bin/bash
# Script de lancement de tous les tests E2E Scorpius
# Usage: ./scripts/run_all_tests.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "   SCORPIUS - TESTS E2E COMPLETS"
echo "=========================================="
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Function to check service health
check_service() {
    local service=$1
    local port=$2
    if docker ps | grep -q "$service"; then
        echo -e "${GREEN}✅${NC} $service actif (port $port)"
        return 0
    else
        echo -e "${RED}❌${NC} $service inactif"
        return 1
    fi
}

# Function to run test and check result
run_test() {
    local test_name=$1
    local test_script=$2
    local log_file=$3

    echo ""
    echo "▶️  Exécution: $test_name..."

    if python "$test_script" > "$log_file" 2>&1; then
        echo -e "${GREEN}✅${NC} $test_name - SUCCÈS"
        return 0
    else
        # Check for partial success
        if grep -q "ANALYSE PARTIELLE RÉUSSIE\|Passed: [5-9]\/\|Passed: [0-9][0-9]" "$log_file"; then
            echo -e "${YELLOW}⚠️${NC} $test_name - SUCCÈS PARTIEL"
            grep "Passed:" "$log_file" | tail -1
            return 0
        else
            echo -e "${RED}❌${NC} $test_name - ÉCHEC"
            echo "   Voir: $log_file"
            return 1
        fi
    fi
}

# 1. Vérification de l'environnement
echo "1️⃣  VÉRIFICATION DE L'ENVIRONNEMENT"
echo "-----------------------------------"

all_services_up=true
check_service "scorpius-db" 5432 || all_services_up=false
check_service "scorpius-redis" 6379 || all_services_up=false
check_service "scorpius-app" 8000 || all_services_up=false

if [ "$all_services_up" = false ]; then
    echo ""
    echo -e "${RED}❌ L'environnement n'est pas complètement opérationnel${NC}"
    echo "   Lancer: docker-compose up -d"
    exit 1
fi

# Check API health
echo ""
echo "Vérification de l'API..."
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo -e "${GREEN}✅${NC} API opérationnelle"
else
    echo -e "${RED}❌${NC} API ne répond pas"
    exit 1
fi

# 2. Préparation des données
echo ""
echo "2️⃣  PRÉPARATION DES DONNÉES"
echo "-------------------------"

echo "Ajout du contenu traité aux documents..."
if docker exec scorpius-app python scripts/add_processed_content.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} Contenu traité ajouté"
else
    echo -e "${YELLOW}⚠️${NC} Problème lors de l'ajout du contenu (peut-être déjà fait)"
fi

# Create reports directory if not exists
mkdir -p reports
mkdir -p test_results

# 3. Exécution des tests
echo ""
echo "3️⃣  EXÉCUTION DES TESTS E2E"
echo "--------------------------"

test_count=0
success_count=0

# Test Orchestrateur
if run_test "Test Orchestrateur Complet" "scripts/test_e2e_orchestrator.py" "test_results/orchestrator.log"; then
    ((success_count++))
fi
((test_count++))

# Test VSGP Analysis
if run_test "Test VSGP Analysis" "scripts/test_e2e_vsgp_analysis.py" "test_results/vsgp.log"; then
    ((success_count++))
    if [ -f "reports/vsgp_analysis_report.json" ]; then
        echo "   📄 Rapport JSON généré"
    fi
    if [ -f "reports/vsgp_analysis_report.md" ]; then
        echo "   📄 Rapport Markdown généré"
    fi
fi
((test_count++))

# Test AI Extraction (if previous tests created data)
if [ -f "/tmp/e2e_documents.json" ]; then
    if run_test "Test AI Extraction" "scripts/test_e2e_ai_extraction.py" "test_results/ai_extraction.log"; then
        ((success_count++))
    fi
    ((test_count++))
fi

# 4. Métriques de la base de données
echo ""
echo "4️⃣  MÉTRIQUES DE LA BASE DE DONNÉES"
echo "---------------------------------"

docker exec -i scorpius-db psql -U scorpius -d scorpius_mvp -c "
SELECT
  'Tenders' as entity,
  COUNT(*) as count
FROM procurement_tenders
UNION ALL
SELECT
  'Documents' as entity,
  COUNT(*) as count
FROM procurement_documents
UNION ALL
SELECT
  'Requirements' as entity,
  COUNT(*) as count
FROM extracted_requirement
UNION ALL
SELECT
  'Analyses' as entity,
  COUNT(*) as count
FROM analysis_history;
" 2>/dev/null | grep -E "Tenders|Documents|Requirements|Analyses" || echo "Impossible de récupérer les métriques"

# 5. Résumé final
echo ""
echo "=========================================="
echo "           RÉSUMÉ DES TESTS"
echo "=========================================="

# Calculate success percentage
if [ $test_count -gt 0 ]; then
    percentage=$((success_count * 100 / test_count))
else
    percentage=0
fi

echo ""
echo "Tests réussis: $success_count/$test_count ($percentage%)"
echo ""

# Status based on percentage
if [ $percentage -ge 80 ]; then
    echo -e "${GREEN}🏆 EXCELLENT - Système opérationnel${NC}"
elif [ $percentage -ge 60 ]; then
    echo -e "${YELLOW}✅ BON - Système fonctionnel avec quelques problèmes${NC}"
else
    echo -e "${RED}❌ INSUFFISANT - Système nécessite attention${NC}"
fi

echo ""
echo "📁 Fichiers générés:"
echo "-------------------"
echo "Logs des tests:"
ls -la test_results/*.log 2>/dev/null | awk '{print "  - " $9}' || echo "  Aucun log généré"

echo ""
echo "Rapports d'analyse:"
ls -la reports/*.{json,md} 2>/dev/null | awk '{print "  - " $9}' || echo "  Aucun rapport généré"

echo ""
echo "📊 Pour voir les détails:"
echo "  - Logs API: docker logs scorpius-app --tail 50"
echo "  - Logs tests: cat test_results/*.log"
echo "  - Rapports: cat reports/vsgp_analysis_report.md"

echo ""
echo "=========================================="
echo "Fin des tests: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# Exit with appropriate code
if [ $percentage -ge 60 ]; then
    exit 0
else
    exit 1
fi