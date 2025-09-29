# Guide de Test Multi-Documents VSGP-AO-2024

## 🎯 Actions Correctives Appliquées

### ✅ **1. Dépendances AI Fixes**
- Ajout de `pgvector==0.4.1` dans `requirements.txt`
- Toutes les dépendances ML/AI déclarées
- Plus de `ModuleNotFoundError` au démarrage

### ✅ **2. Configuration Base de Données**
- Script `scripts/init_db_complete.py` pour initialisation complète
- Extension pgvector activée automatiquement
- Script SQL `scripts/001_init_extensions.sql`
- Configuration auth améliorée dans docker-compose.yml

### ✅ **3. Script de Démarrage Robuste**
- `start_test_environment_robust.sh` avec checks complets
- Attente intelligente des services (health checks)
- Gestion d'erreurs et logs détaillés
- Nettoyage automatique avant démarrage

### ✅ **4. Tests Graduels**
- Tests de base sans DB : `test_endpoints_basic.py`
- Tests complets : `test_multi_document_analysis.py`
- Validation progressive des fonctionnalités

## 🚀 **Procédure de Test Recommandée**

### **Étape 1: Démarrage Propre**
```bash
# Nettoyer l'environnement existant
docker-compose down --remove-orphans --volumes

# Démarrer avec le script robuste
./start_test_environment_robust.sh
```

### **Étape 2: Validation Progressive**
```bash
# 1. Test des endpoints de base
python test_endpoints_basic.py

# 2. Vérification santé API
curl http://localhost:8000/api/v1/health | jq

# 3. Test complet multi-documents
python test_multi_document_analysis.py
```

### **Étape 3: Validation Manuelle**
- Interface docs : http://localhost:8000/api/v1/docs
- pgAdmin : http://localhost:5050 (admin@admin.com / admin)
- Vérifier les tables : `\dt` dans psql

## 🔧 **Résolution des Problèmes Persistants**

### **Si la DB ne démarre pas :**
```bash
# Supprimer complètement les volumes
docker-compose down -v
docker volume prune -f

# Redémarrer
./start_test_environment_robust.sh
```

### **Si les dépendances AI manquent :**
```bash
# Rebuild complet du conteneur
docker-compose build --no-cache app
docker-compose up -d app
```

### **Si l'authentification échoue :**
```bash
# Recréer la DB avec les bons credentials
docker-compose exec db dropdb -U scorpius scorpius_mvp
docker-compose exec db createdb -U scorpius scorpius_mvp
docker-compose exec app python /app/scripts/init_db_complete.py
```

## 📊 **Points de Contrôle de Validation**

### ✅ **Infrastructure**
- [ ] Docker services démarrés (db, redis, app)
- [ ] API répond sur http://localhost:8000/health
- [ ] Documentation accessible sur /api/v1/docs
- [ ] 37 endpoints détectés dans OpenAPI schema

### ✅ **Base de Données**
- [ ] Connection PostgreSQL réussie
- [ ] Extension pgvector activée
- [ ] 9+ tables créées (users, documents, tenders, etc.)
- [ ] Health check DB = "healthy"

### ✅ **Tests Fonctionnels**
- [ ] Authentification utilisateur
- [ ] Création de tender VSGP-AO-2024
- [ ] Upload des 3 documents (RC, CCAP, CCTP)
- [ ] Traitement automatique des documents
- [ ] Analyse consolidée du tender

## 🎉 **Objectif Final**

**Test complet réussi** avec :
- ✅ Tender "VSGP-AO-2024" créé
- ✅ 3 documents traités et analysés
- ✅ Rapport de test généré
- ✅ Temps total < 5 minutes

## 📞 **Support**

En cas de problème persistant :
1. Consulter les logs : `docker-compose logs -f app`
2. Vérifier la santé : `curl http://localhost:8000/api/v1/health`
3. Nettoyer complètement : `docker-compose down -v`