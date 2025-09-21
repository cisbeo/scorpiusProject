"""Main application entry point for Scorpius Project API."""

import uvicorn

from src.api.v1.app import app
from src.core.config import get_settings


def main():
    """Run the FastAPI application with uvicorn."""
    settings = get_settings()

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.api_workers,
        log_level=settings.log_level.lower(),
        access_log=True,
        use_colors=True,
        reload_dirs=["src"] if settings.is_development else None,
    )


if __name__ == "__main__":
    main()