"""
Main FastAPI application entry point with enhanced error handling and logging.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database.mysql_client import mysql_client
from app.database.milvus_client import milvus_client
from app.api.v1 import summarize, translate, documents, legacy
from app.utils.logging import setup_logging
from loguru import logger
import time

settings = get_settings()

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Agentic AI Server...")
    logger.info(f"Environment: {'DEBUG' if settings.DEBUG else 'PRODUCTION'}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")
    
    # Initialize database
    try:
        mysql_client.init_database()
        logger.info("MySQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MySQL: {e}")
    
    # Initialize Milvus collection
    try:
        milvus_client.create_collection()
        logger.info("Milvus collection initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Milvus: {e}")
    
    logger.success("Agentic AI Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Agentic AI Server...")
    try:
        mysql_client.close()
        milvus_client.close()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    description="LangGraph + MySQL + Redis + Milvus based Agentic AI Server with async task queue",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    logger.info(f"Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        logger.info(f"Response: {response.status_code} | Time: {process_time:.3f}s | Path: {request.url.path}")
        
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} | Error: {str(e)}")
        raise


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "path": request.url.path
        }
    )


# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(f"Validation error: {request.url.path} | Errors: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": exc.errors(),
            "path": request.url.path
        }
    )


# Include API routers
app.include_router(summarize.router, prefix=f"/api/{settings.API_VERSION}", tags=["Summarize"])
app.include_router(translate.router, prefix=f"/api/{settings.API_VERSION}", tags=["Translate"])
app.include_router(documents.router, prefix=f"/api/{settings.API_VERSION}", tags=["Documents"])
app.include_router(legacy.router, prefix=f"/api/{settings.API_VERSION}", tags=["Legacy Data"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "features": {
            "async_tasks": True,
            "caching": True,
            "korean_optimization": settings.ENABLE_KOREAN_OPTIMIZATION,
            "smart_chunking": True
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with detailed service status."""
    from app.database.redis_client import redis_client
    
    services = {
        "mysql": False,
        "redis": False,
        "milvus": False
    }
    
    # Check MySQL
    try:
        session = mysql_client.get_session()
        session.execute("SELECT 1")
        session.close()
        services["mysql"] = True
        logger.debug("MySQL health check: OK")
    except Exception as e:
        logger.error(f"MySQL health check failed: {e}")
    
    # Check Redis
    try:
        services["redis"] = redis_client.ping()
        logger.debug("Redis health check: OK")
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
    
    # Check Milvus
    try:
        milvus_client.get_collection_stats()
        services["milvus"] = True
        logger.debug("Milvus health check: OK")
    except Exception as e:
        logger.error(f"Milvus health check failed: {e}")
    
    all_healthy = all(services.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "version": settings.API_VERSION,
            "services": services,
            "features": {
                "async_queue": True,
                "query_cache": settings.ENABLE_QUERY_CACHE,
                "korean_optimization": settings.ENABLE_KOREAN_OPTIMIZATION
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_config=None  # Use our custom logging
    )
