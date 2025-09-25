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
