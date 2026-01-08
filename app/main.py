"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database.mysql_client import mysql_client
from app.database.milvus_client import milvus_client
from app.api.v1 import summarize, translate, documents, legacy

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    # Startup
    print("Starting Agentic AI Server...")
    
    # Initialize database
    try:
        mysql_client.init_database()
        print("MySQL database initialized")
    except Exception as e:
        print(f"Failed to initialize MySQL: {e}")
    
    # Initialize Milvus collection
    try:
        milvus_client.create_collection()
        print("Milvus collection initialized")
    except Exception as e:
        print(f"Failed to initialize Milvus: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down Agentic AI Server...")
    try:
        mysql_client.close()
        milvus_client.close()
    except Exception as e:
        print(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    description="LangGraph + MySQL + Redis + Milvus based Agentic AI Server",
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
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
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
    except Exception as e:
        print(f"MySQL health check failed: {e}")
    
    # Check Redis
    try:
        services["redis"] = redis_client.ping()
    except Exception as e:
        print(f"Redis health check failed: {e}")
    
    # Check Milvus
    try:
        milvus_client.get_collection_stats()
        services["milvus"] = True
    except Exception as e:
        print(f"Milvus health check failed: {e}")
    
    all_healthy = all(services.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "version": settings.API_VERSION,
            "services": services
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
