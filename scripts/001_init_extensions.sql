-- Script d'initialisation des extensions PostgreSQL
-- Ce script est exécuté automatiquement au démarrage du conteneur

-- Activer l'extension pgvector pour les embeddings vectoriels
CREATE EXTENSION IF NOT EXISTS vector;

-- Activer l'extension uuid pour la génération d'UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log des extensions installées
SELECT
    extname AS extension_name,
    extversion AS version
FROM pg_extension
WHERE extname IN ('vector', 'uuid-ossp');