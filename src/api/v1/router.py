"""API v1 router configuration."""

from fastapi import APIRouter

from src.api.v1.endpoints import analysis, auth, company, documents, health, tenders, upload_async, search, rag

# Create main v1 router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router)
api_router.include_router(tenders.router)
api_router.include_router(documents.router)
api_router.include_router(company.router)
api_router.include_router(analysis.router)
api_router.include_router(health.router)
api_router.include_router(upload_async.router)
api_router.include_router(search.router)
api_router.include_router(rag.router, prefix="/rag", tags=["RAG"])
