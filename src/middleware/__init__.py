"""Middleware for FastAPI application."""

from src.middleware.auth import AuthMiddleware

__all__ = [
    "AuthMiddleware",
]
