"""Health check endpoints for system monitoring."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.session import get_async_db
from src.processors import processor_factory
from src.services.document import DocumentPipelineService

# Create router for health endpoints
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="System health check",
    description="Check the health status of all system components",
    responses={
        200: {
            "description": "System is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "version": "1.0.0",
                        "environment": "development",
                        "components": {
                            "database": {"status": "healthy", "response_time_ms": 15},
                            "processors": {"status": "healthy", "available": ["PyPDF2Processor"]},
                            "storage": {"status": "healthy", "upload_path_writable": True},
                            "pipeline": {"status": "healthy", "version": "1.0.0"}
                        },
                        "metrics": {
                            "uptime_seconds": 3600,
                            "memory_usage_mb": 256,
                            "active_connections": 5
                        }
                    }
                }
            }
        },
        503: {
            "description": "System is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "components": {
                            "database": {"status": "unhealthy", "error": "Connection timeout"},
                            "processors": {"status": "healthy", "available": ["PyPDF2Processor"]},
                            "storage": {"status": "unhealthy", "error": "Upload directory not writable"},
                            "pipeline": {"status": "healthy", "version": "1.0.0"}
                        }
                    }
                }
            }
        }
    }
)
async def health_check(db: AsyncSession = Depends(get_async_db)):
    """
    Comprehensive health check for all system components.

    **Checks include:**
    - Database connectivity and response time
    - Document processors availability
    - Storage system accessibility
    - Pipeline service status
    - System metrics

    **Response format:**
    ```json
    {
        "status": "healthy|unhealthy",
        "timestamp": "ISO timestamp",
        "version": "application version",
        "environment": "development|staging|production",
        "components": {
            "database": {"status": "...", ...},
            "processors": {"status": "...", ...},
            "storage": {"status": "...", ...},
            "pipeline": {"status": "...", ...}
        },
        "metrics": {
            "uptime_seconds": 3600,
            "memory_usage_mb": 256,
            "active_connections": 5
        }
    }
    ```

    Returns HTTP 200 if all components are healthy, HTTP 503 if any critical component is down.
    """
    settings = get_settings()
    health_result = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",  # Could be read from package version
        "environment": settings.app_env,
        "components": {},
        "metrics": {}
    }

    overall_healthy = True

    # Check database connectivity
    db_health = await _check_database_health(db)
    health_result["components"]["database"] = db_health
    if db_health["status"] != "healthy":
        overall_healthy = False

    # Check document processors
    processor_health = await _check_processors_health()
    health_result["components"]["processors"] = processor_health
    if processor_health["status"] != "healthy":
        overall_healthy = False

    # Check storage system
    storage_health = await _check_storage_health()
    health_result["components"]["storage"] = storage_health
    if storage_health["status"] != "healthy":
        overall_healthy = False

    # Check pipeline service
    pipeline_health = await _check_pipeline_health(db)
    health_result["components"]["pipeline"] = pipeline_health
    if pipeline_health["status"] != "healthy":
        overall_healthy = False

    # Add system metrics
    health_result["metrics"] = await _get_system_metrics()

    # Set overall status
    health_result["status"] = "healthy" if overall_healthy else "unhealthy"

    # Return appropriate HTTP status
    response_status = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=health_result,
        status_code=response_status
    )


async def _check_database_health(db: AsyncSession) -> dict:
    """Check database connectivity and performance."""
    try:
        start_time = datetime.utcnow()

        # Simple database query
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))

        end_time = datetime.utcnow()
        response_time = int((end_time - start_time).total_seconds() * 1000)

        return {
            "status": "healthy",
            "response_time_ms": response_time,
            "connection_pool": "active"
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": None
        }


async def _check_processors_health() -> dict:
    """Check document processors availability."""
    try:
        available_processors = processor_factory.list_processors()
        supported_types = processor_factory.get_supported_types()

        if not available_processors:
            return {
                "status": "unhealthy",
                "error": "No processors available",
                "available": []
            }

        # Test each processor
        healthy_processors = []
        for processor_name in available_processors:
            processor = processor_factory.get_processor(processor_name)
            if processor:
                try:
                    health_check = await processor.health_check()
                    if health_check.get("status") == "healthy":
                        healthy_processors.append(processor_name)
                except Exception:
                    pass

        return {
            "status": "healthy" if healthy_processors else "unhealthy",
            "available": healthy_processors,
            "total_registered": len(available_processors),
            "supported_types": len(supported_types)
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "available": []
        }


async def _check_storage_health() -> dict:
    """Check storage system accessibility."""
    try:
        from src.services.document import DocumentStorageService

        storage_service = DocumentStorageService()
        storage_info = storage_service.get_storage_info()

        if "error" in storage_info:
            return {
                "status": "unhealthy",
                "error": storage_info["error"]
            }

        # Check if directories are writable
        upload_writable = storage_info.get("upload_path_writable", False)
        temp_writable = storage_info.get("temp_path_writable", False)

        if not upload_writable or not temp_writable:
            return {
                "status": "unhealthy",
                "error": "Storage directories not writable",
                "upload_path_writable": upload_writable,
                "temp_path_writable": temp_writable
            }

        return {
            "status": "healthy",
            "upload_path": storage_info["upload_path"],
            "temp_path": storage_info["temp_path"],
            "upload_path_writable": upload_writable,
            "temp_path_writable": temp_writable
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _check_pipeline_health(db: AsyncSession) -> dict:
    """Check document processing pipeline health."""
    try:
        pipeline_service = DocumentPipelineService(db)
        pipeline_health = await pipeline_service.health_check()

        return {
            "status": pipeline_health.get("status", "unknown"),
            "service": pipeline_health.get("service", "DocumentPipelineService"),
            "processors_available": pipeline_health.get("processors_available", []),
            "storage_info": pipeline_health.get("storage_info", {}),
            "validation_service": pipeline_health.get("validation_service", "unknown")
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _get_system_metrics() -> dict:
    """Get basic system metrics."""
    try:
        import time

        import psutil

        # Get process info
        process = psutil.Process()

        # Calculate uptime (simplified - in production you'd track from app start)
        uptime_seconds = int(time.time() - process.create_time())

        # Memory usage
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024

        # Connection count (simplified)
        connections = len(process.connections())

        return {
            "uptime_seconds": uptime_seconds,
            "memory_usage_mb": round(memory_mb, 1),
            "active_connections": connections,
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads()
        }

    except Exception:
        # Fallback metrics if psutil not available
        return {
            "uptime_seconds": "unknown",
            "memory_usage_mb": "unknown",
            "active_connections": "unknown",
            "cpu_percent": "unknown",
            "threads": "unknown"
        }


@router.get(
    "/health/db",
    status_code=status.HTTP_200_OK,
    summary="Database health check",
    description="Check database connectivity and status",
    responses={
        200: {"description": "Database is healthy"},
        503: {"description": "Database is unhealthy"}
    }
)
async def check_database_health(db: AsyncSession = Depends(get_async_db)):
    """
    Check database health status.

    Returns database connectivity and response time.
    """
    health_status = await _check_database_health(db)

    if health_status["status"] == "healthy":
        return health_status
    else:
        return health_status


@router.get(
    "/health/cache",
    status_code=status.HTTP_200_OK,
    summary="Redis cache health check",
    description="Check Redis cache connectivity and status",
    responses={
        200: {"description": "Cache is healthy"},
        503: {"description": "Cache is unhealthy"}
    }
)
async def check_cache_health():
    """
    Check Redis cache health status.

    Returns cache connectivity status.
    """
    try:
        import redis.asyncio as redis
        from src.core.config import get_settings

        settings = get_settings()

        # Try to connect to Redis
        redis_url = settings.get_redis_url()
        redis_client = redis.from_url(
            redis_url,
            decode_responses=True
        )

        # Test connection with ping
        await redis_client.ping()
        await redis_client.close()

        return {
            "status": "healthy",
            "message": "Redis cache is operational",
            "url": redis_url.replace(":6379", ":****")  # Hide port for security
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Redis cache connection failed"
        }


@router.get(
    "/health/ai",
    status_code=status.HTTP_200_OK,
    summary="AI service health check",
    description="Check Mistral AI API connectivity and configuration",
    responses={
        200: {"description": "AI service is healthy"},
        503: {"description": "AI service is unhealthy or not configured"}
    }
)
async def check_ai_health():
    """
    Check Mistral AI API health and configuration.

    Returns AI service availability status.
    """
    try:
        from src.core.config import get_settings

        settings = get_settings()

        # Check if API key is configured
        if not settings.mistral_api_key:
            return {
                "status": "not_configured",
                "message": "Mistral AI API key not configured",
                "configured": False
            }

        # Check if the key looks valid (basic check)
        if len(settings.mistral_api_key) < 20:
            return {
                "status": "misconfigured",
                "message": "Invalid Mistral AI API key format",
                "configured": False
            }

        # Could add actual API ping here if needed
        # For now, just verify configuration
        return {
            "status": "healthy",
            "message": "Mistral AI service is configured",
            "configured": True,
            "api_key_present": True,
            "api_key_length": len(settings.mistral_api_key)
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to check AI service: {str(e)}",
            "configured": False
        }
