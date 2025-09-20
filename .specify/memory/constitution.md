<!--
Sync Impact Report:
Version change: new → 1.0.0
Project: ScorpiusProject - French Public Procurement Document Analysis Backend
Added sections: All sections (new constitution)
Templates requiring updates: ✅ plan-template.md, ✅ spec-template.md, ✅ tasks-template.md compatible
Follow-up TODOs: None
-->

# ScorpiusProject Constitution

## Core Principles

### I. Data Pipeline Integrity

Document ingestion and processing pipelines MUST be idempotent and recoverable. Every document processing stage MUST log structured metadata (document_id, stage, timestamp, status). Failed documents MUST be retryable without data corruption. Pipeline state MUST be externally observable through health endpoints.

### II. NLP Model Reproducibility

All NLP models and embeddings MUST use pinned versions and deterministic processing. Model inference MUST include confidence scores and processing metadata. Vector embeddings MUST be versioned and migrations MUST be backward compatible. No production model changes without A/B testing validation.

Rationale: AI-generated procurement responses must be consistent, traceable, and legally defensible.

### III. API-First Architecture

Every service functionality MUST be exposed via FastAPI REST endpoints with OpenAPI documentation. All endpoints MUST implement standardized error responses, request validation, and structured logging. Internal service communication MUST use the same API contracts as external clients.

Rationale: Enables integration testing, client SDK generation, and service modularity for complex document workflows.

### IV. Knowledge Base Consistency

RAG knowledge base updates MUST be atomic operations with rollback capability. Vector search results MUST include source document provenance and retrieval confidence. Knowledge updates MUST not affect in-flight document processing. Vector index state MUST be externally verifiable.

Rationale: Procurement response quality depends on consistent, auditable knowledge retrieval across document processing sessions.

## Performance Standards

Python services MUST handle 1000+ concurrent document uploads with <5s p95 processing latency. Vector searches MUST return results within 200ms p95. Memory usage MUST not exceed 8GB per service instance under normal load. All databases MUST use connection pooling and prepared statements.

Rationale: Real-time procurement deadline requirements demand predictable performance characteristics.

## Development Workflow

TDD is mandatory: write failing tests, implement to pass, refactor. All PRs MUST include integration tests for new endpoints. Database migrations MUST be tested with production-scale data volumes. Pre-commit hooks MUST run linting (ruff), type checking (mypy), and security scanning (bandit).

Code reviews MUST verify: API contract compatibility, vector embedding versioning impact, data pipeline idempotency, and security controls implementation.

## Governance

This constitution supersedes all other development practices. Constitutional violations require explicit justification and technical debt documentation.

All PRs MUST verify constitutional compliance through automated checks. Complexity additions MUST demonstrate clear business value and simpler alternatives consideration.

Amendment procedure: propose changes via issue, achieve consensus, update all dependent templates, increment version following semantic versioning.

**Version**: 1.0.0 | **Ratified**: 2025-09-20 | **Last Amended**: 2025-09-20
