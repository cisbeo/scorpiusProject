# 🐳 Docker Cloud Deployment Guide

## Overview
This guide explains how to build and deploy Scorpius with Docling using GitHub Container Registry (ghcr.io).

## 🚀 Automatic Build & Deploy

### 1. GitHub Actions Workflow
The project uses GitHub Actions to automatically build and push Docker images when:
- Code is pushed to `main` or `develop` branches
- A pull request is created
- Manual trigger via GitHub Actions UI

### 2. Image Registry
Images are published to GitHub Container Registry:
```
ghcr.io/[your-username]/scorpiusproject-docling:latest
```

## 📋 Setup Instructions

### Prerequisites
1. GitHub repository with Actions enabled
2. Docker installed locally for testing
3. Access to production server

### Initial Setup

1. **Update GitHub Actions workflow** (if needed):
   Edit `.github/workflows/docker-build-push.yml` to match your repository name.

2. **First build trigger**:
   ```bash
   git add .
   git commit -m "feat: Add Docker Cloud build with Docling"
   git push origin main
   ```

3. **Monitor build progress**:
   - Go to GitHub → Actions tab
   - Watch the "Build and Push Docker Image" workflow

## 🖥️ Local Development

### Using pre-built image from ghcr.io:
```bash
# Pull latest image
docker pull ghcr.io/[your-username]/scorpiusproject-docling:latest

# Run with docker-compose
docker-compose -f docker-compose.ghcr.yml up
```

### Building locally for testing:
```bash
# Build optimized image
docker build -f Dockerfile.docling-optimized -t scorpius-docling:local .

# Test locally
docker run -p 8000:8000 scorpius-docling:local
```

## 🌐 Production Deployment

### On your production server (Infomaniak):

1. **Create environment file**:
   ```bash
   cat > .env.production << EOF
   JWT_SECRET_KEY=your-production-secret-key
   DB_PASSWORD=strong-database-password
   PGADMIN_EMAIL=admin@scorpius.com
   PGADMIN_PASSWORD=strong-admin-password
   EOF
   ```

2. **Pull and run the latest image**:
   ```bash
   # Login to GitHub Container Registry (first time only)
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

   # Pull latest image
   docker pull ghcr.io/[your-username]/scorpiusproject-docling:latest

   # Start services
   docker-compose -f docker-compose.ghcr.yml --env-file .env.production up -d
   ```

3. **Update to new version**:
   ```bash
   # Pull latest
   docker-compose -f docker-compose.ghcr.yml pull

   # Restart with new image
   docker-compose -f docker-compose.ghcr.yml up -d --force-recreate
   ```

## 🏗️ Architecture

### Multi-stage Docker Build
The optimized Dockerfile uses a 2-stage build:
1. **Builder stage**: Installs all dependencies and builds artifacts
2. **Runtime stage**: Minimal image with only runtime requirements

### Benefits:
- ✅ Smaller final image (~50% reduction)
- ✅ Faster deployments
- ✅ Better security (no build tools in production)
- ✅ Cached layers for faster rebuilds

## 📊 Image Tags

The workflow creates multiple tags:
- `latest`: Latest from main branch
- `develop`: Latest from develop branch
- `main-SHA-YYYYMMDD`: Specific build with date
- `pr-123`: Pull request builds

## 🔧 Troubleshooting

### Build fails on GitHub Actions
1. Check Actions logs for specific error
2. Ensure all dependencies are specified in requirements files
3. Verify Dockerfile syntax

### Image pull fails on production
```bash
# Re-authenticate with GitHub
docker logout ghcr.io
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

### Docling not working
```bash
# Check logs
docker-compose logs app | grep -i docling

# Verify installation inside container
docker-compose exec app python -c "import docling; print('OK')"
```

## 🔒 Security Notes

1. **Never commit secrets** to the repository
2. Use environment variables for sensitive data
3. Regularly update base images for security patches
4. Use read-only mounts where possible

## 📈 Performance Optimization

1. **Use BuildKit cache**: Enabled in the workflow
2. **Multi-platform builds**: Supports AMD64 and ARM64
3. **Layer caching**: Dependencies installed in order of change frequency
4. **Health checks**: Automatic container restart on failure

## 🔄 Continuous Deployment

To enable auto-deploy to production:
1. Add server SSH key as GitHub Secret
2. Add deployment step to workflow
3. Use webhook or scheduled job to pull latest image

## 📝 Commands Reference

```bash
# View available images
docker images | grep scorpius

# Check running containers
docker-compose -f docker-compose.ghcr.yml ps

# View logs
docker-compose -f docker-compose.ghcr.yml logs -f app

# Restart services
docker-compose -f docker-compose.ghcr.yml restart

# Stop everything
docker-compose -f docker-compose.ghcr.yml down

# Remove old images
docker image prune -a -f
```

## 🎯 Next Steps

1. Push code to trigger first automated build
2. Test image locally using docker-compose.ghcr.yml
3. Deploy to production server
4. Set up monitoring and alerts
5. Configure automated backups

---
*Last updated: 2025-09-24*