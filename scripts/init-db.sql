-- Database initialization script for PostgreSQL

-- Create user if not exists
DO
$$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_user
      WHERE usename = 'scorpius') THEN
      CREATE USER scorpius WITH PASSWORD 'scorpius';
   END IF;
END
$$;

-- Create database if not exists
SELECT 'CREATE DATABASE scorpius_mvp OWNER scorpius'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'scorpius_mvp')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE scorpius_mvp TO scorpius;

-- Connect to the database and enable extensions
\c scorpius_mvp;

-- Enable pgvector extension for future embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";