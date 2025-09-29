# Test Complet d'Analyse Multi-Documents VSGP-AO-2024

## 📁 **Contenu du Répertoire**

### **Scripts de Test**
- **`test_multi_document_analysis.py`** : Test complet end-to-end avec authentification, tender, upload et analyse
- **`test_endpoints_basic.py`** : Test de validation des endpoints sans dépendance DB
- **`test_basic_api.py`** : Test basique des fonctionnalités core API

### **Scripts d'Infrastructure**
- **`start_test_environment_robust.sh`** : Démarrage robuste de l'environnement de test
- **`init_db_complete.py`** : Initialisation complète de la base de données

### **Documentation**
- **`TESTING_GUIDE.md`** : Guide complet des procédures de test et résolution de problèmes

## 🚀 **Utilisation Rapide**

### **Option 1: Démarrage depuis testComplet (Recommandé)**
```bash
cd tests/testComplet
./start_from_testComplet.sh
```

### **Option 2: Exécution complète automatisée**
```bash
cd tests/testComplet
./run_tests.sh
```

### **Option 3: Tests manuels**
```bash
# Démarrer l'environnement
./start_from_testComplet.sh

# Tests individuels
python test_endpoints_basic.py       # Test de base (sans DB)
python test_multi_document_analysis.py  # Test complet multi-documents
```

## 📋 **Prérequis**

- Docker et Docker Compose installés
- Python 3.11+ avec pip
- Accès aux documents de test dans `../../Examples/VSGP-AO/`

## 📊 **Résultats Attendus**

- **37 endpoints API** détectés et fonctionnels
- **Tender VSGP-AO-2024** créé avec succès
- **3 documents** (RC, CCAP, CCTP) uploadés et traités
- **Analyse consolidée** du dossier d'appel d'offres
- **Rapport JSON** généré avec métriques complètes

## 📞 **Support**

Consulter `TESTING_GUIDE.md` pour la résolution des problèmes et le dépannage détaillé.