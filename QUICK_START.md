# 🚀 Guide de Démarrage Rapide - Scorpius Production

## Déploiement Express (30 minutes)

### 📋 Prérequis

- Serveur Ubuntu 22.04+ avec accès root
- Nom de domaine pointant vers le serveur
- 4GB RAM minimum, 2 CPU, 100GB stockage

### ⚡ Déploiement en 5 étapes

#### 1. Préparation du serveur

```bash
# Connexion au serveur
ssh root@votre-serveur.fr

# Installation Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Installation Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Création utilisateur scorpius
useradd -m -s /bin/bash scorpius
usermod -aG docker scorpius
```

#### 2. Déploiement de l'application

```bash
# Connexion utilisateur scorpius
sudo su - scorpius

# OPTION A: Transfert depuis machine locale (recommandé)
# Depuis votre machine de dev : tar -czf scorpius.tar.gz . --exclude='.git'
# Puis : scp scorpius.tar.gz scorpius@votre-serveur:/tmp/
sudo tar -xzf /tmp/scorpius.tar.gz -C /opt
sudo chown -R scorpius:scorpius /opt/scorpius-project
cd /opt/scorpius-project

# OPTION B: Clone Git avec token personnel
# git clone https://USERNAME:TOKEN@github.com/votre-org/scorpius-project.git
# cd scorpius-project

# Initialisation
./deploy.sh init

# IMPORTANT: Éditer .env.prod avec votre domaine
nano .env.prod
# Modifier: CORS_ORIGINS=["https://votre-domaine.fr"]
```

#### 3. Configuration SSL (Let's Encrypt)

```bash
# Installation Certbot
sudo snap install --classic certbot

# Génération certificats
sudo certbot certonly --standalone -d votre-domaine.fr

# Copie des certificats
sudo cp /etc/letsencrypt/live/votre-domaine.fr/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/votre-domaine.fr/privkey.pem nginx/ssl/key.pem
sudo chown scorpius:scorpius nginx/ssl/*
```

#### 4. Démarrage des services

```bash
# Démarrage complet
./deploy.sh start

# Vérification du statut
./deploy.sh status
```

#### 5. Test de l'installation

```bash
# Test API
curl -X GET https://votre-domaine.fr/health

# Test interface documentation
# Ouvrir: https://votre-domaine.fr/api/v1/docs
```

### 🔧 Configuration rapide

#### Création utilisateur admin

```bash
docker-compose -f docker-compose.prod.yml exec api python -c "
import asyncio
from src.services.auth.auth_service import AuthService
from src.db.session import get_async_db

async def create_admin():
    async for db in get_async_db():
        auth_service = AuthService(db)
        user = await auth_service.register_user(
            email='admin@votre-domaine.fr',
            password='AdminScorpius2024!',
            full_name='Administrateur Scorpius',
            role='admin'
        )
        print(f'✅ Utilisateur admin créé: {user.email}')
        break

asyncio.run(create_admin())
"
```

#### Test complet du système

```bash
# Test enregistrement utilisateur
curl -X POST https://votre-domaine.fr/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!",
    "full_name": "Utilisateur Test",
    "role": "bid_manager"
  }'

# Test connexion
curl -X POST https://votre-domaine.fr/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123!"
  }'
```

## 📊 Monitoring Simplifié

### Commandes de surveillance

```bash
# Statut général
./deploy.sh status

# Logs en temps réel
./deploy.sh logs

# Santé des services
./deploy.sh health

# Sauvegarde base de données
./deploy.sh backup
```

### Métriques importantes

```bash
# Utilisation disque
df -h

# Mémoire
free -h

# CPU et processus
htop

# Logs système
journalctl -fu docker
```

## 🔒 Sécurité Express

### Firewall basique

```bash
# Configuration UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Renouvellement SSL automatique

```bash
# Ajout au crontab
sudo crontab -e

# Ajouter cette ligne:
0 3 * * * certbot renew --quiet --deploy-hook "systemctl reload nginx"
```

## 🚨 Dépannage Rapide

### Services ne démarrent pas

```bash
# Vérifier les logs
./deploy.sh logs

# Redémarrer un service spécifique
docker-compose -f docker-compose.prod.yml restart api

# Reconstruction complète
./deploy.sh stop
./deploy.sh start
```

### Base de données corrompue

```bash
# Restaurer depuis backup
./deploy.sh restore backups/backup_20241201_120000.sql
```

### Problème de performance

```bash
# Vérifier ressources
docker stats

# Redémarrer Redis
docker-compose -f docker-compose.prod.yml restart redis
```

## 📱 Tests utilisateurs

### Scénarios de test

#### 1. Inscription et connexion

- ✅ Créer compte utilisateur
- ✅ Se connecter avec les identifiants
- ✅ Accéder à l'interface documentation

#### 2. Gestion des documents

- ✅ Uploader un document PDF
- ✅ Traiter le document
- ✅ Consulter les exigences extraites

#### 3. Profil entreprise

- ✅ Créer profil entreprise
- ✅ Ajouter capacités et certifications
- ✅ Mettre à jour les informations

#### 4. Analyse des capacités

- ✅ Lancer analyse de correspondance
- ✅ Consulter recommandations
- ✅ Évaluer score de compatibilité

## 🎯 Prochaines étapes

### Optimisations production

1. **CDN**: Configurer Cloudflare
2. **Monitoring**: Installer Grafana + Prometheus
3. **Backup**: Automatiser sauvegardes S3
4. **Load Balancer**: Ajouter HAProxy
5. **CI/CD**: Pipeline automatisé

### Formation utilisateurs

1. **Documentation**: Guide utilisateur complet
2. **Vidéos**: Tutoriels fonctionnalités clés
3. **Support**: Canal de support technique
4. **FAQ**: Questions fréquentes

---

## ✅ Checklist de mise en production

- [ ] Serveur configuré avec Docker
- [ ] Domaine configuré et SSL actif
- [ ] Application déployée et fonctionnelle
- [ ] Base de données initialisée
- [ ] Utilisateur admin créé
- [ ] Tests fonctionnels validés
- [ ] Monitoring en place
- [ ] Sauvegardes configurées
- [ ] Sécurité de base appliquée
- [ ] Documentation accessible

**🎉 Félicitations ! Scorpius est maintenant en production et prêt pour les tests utilisateurs.**
