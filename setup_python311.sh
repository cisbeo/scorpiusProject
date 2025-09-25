#!/bin/bash

# Script pour configurer l'environnement Python 3.11 avec Docling
# Usage: ./setup_python311.sh

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🐍 Configuration de l'environnement Python 3.11 pour Scorpius + Docling${NC}"
echo "================================================================"

# Vérifier Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo -e "${RED}❌ Python 3.11 n'est pas installé${NC}"
    echo "Installation sur macOS: brew install python@3.11"
    echo "Installation sur Linux: apt-get install python3.11 python3.11-venv"
    exit 1
fi

echo -e "${GREEN}✅ Python 3.11 trouvé: $(python3.11 --version)${NC}"

# Créer l'environnement virtuel
ENV_NAME="venv_311"
if [ -d "$ENV_NAME" ]; then
    echo -e "${BLUE}🔄 Suppression de l'ancien environnement...${NC}"
    rm -rf $ENV_NAME
fi

echo -e "${BLUE}📦 Création de l'environnement virtuel Python 3.11...${NC}"
python3.11 -m venv $ENV_NAME

# Activer l'environnement
source $ENV_NAME/bin/activate

# Mettre à jour pip
echo -e "${BLUE}⬆️  Mise à jour de pip...${NC}"
pip install --upgrade pip setuptools wheel

# Installer les dépendances de base
echo -e "${BLUE}📚 Installation des dépendances de base...${NC}"
pip install -r requirements.txt

# Installer Docling
echo -e "${BLUE}🚀 Installation de Docling...${NC}"
pip install docling

# Installer les dépendances pour LlamaIndex
echo -e "${BLUE}🔗 Installation de LlamaIndex + Docling...${NC}"
pip install llama-index-core llama-index-readers-docling

# Installer les dépendances de test
echo -e "${BLUE}🧪 Installation des outils de développement...${NC}"
pip install pytest pytest-asyncio pytest-cov ruff mypy

# Créer un script d'activation
cat > activate_scorpius.sh << 'EOF'
#!/bin/bash
# Activation de l'environnement Scorpius Python 3.11

source venv_311/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)
export TESSDATA_PREFIX=/usr/local/share/tessdata

echo "✅ Environnement Scorpius Python 3.11 activé"
echo "   Python: $(which python) - $(python --version)"
echo "   Docling: $(pip show docling | grep Version)"
echo ""
echo "📋 Commandes disponibles:"
echo "   • python poc/docling_processor.py   - Tester le processeur Docling"
echo "   • python scripts/test_ccap_25fc17.py - Tester le CCAP"
echo "   • pytest tests/                      - Lancer les tests"
echo "   • deactivate                         - Désactiver l'environnement"
EOF

chmod +x activate_scorpius.sh

echo ""
echo -e "${GREEN}✅ Installation terminée !${NC}"
echo ""
echo "Pour activer l'environnement :"
echo -e "${BLUE}source activate_scorpius.sh${NC}"
echo ""
echo "Pour tester Docling :"
echo -e "${BLUE}python poc/docling_processor.py${NC}"

# Afficher les versions installées
echo ""
echo "📊 Versions installées :"
python --version
pip show docling | grep Version || echo "Docling: Installation en cours..."
pip show fastapi | grep Version
pip show pydantic | grep Version