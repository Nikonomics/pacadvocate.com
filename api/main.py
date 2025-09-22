from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
import logging
import os
import time
from datetime import datetime

# Import routers
from api.routers import auth, bills, alerts, dashboard

# Import middleware
from api.middleware.rate_limiting import RateLimitMiddleware
from api.middleware.redis_client import redis_client

# Import config
from api.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events"""
    # Startup
    logger.info("🚀 Starting SNF Legislation Tracker API")
    logger.info(f"📊 Environment: {'Development' if settings.debug else 'Production'}")
    logger.info(f"🔗 Database: {settings.database_url}")
    logger.info(f"💾 Redis: {settings.redis_url}")

    # Test connections
    try:
        # Test Redis connection
        await redis_client.get_client()
        logger.info("✅ Redis connection established")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")

    yield

    # Shutdown
    logger.info("🛑 Shutting down SNF Legislation Tracker API")
    try:
        await redis_client.close()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing Redis connection: {e}")

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
# SNF Legislation Tracker API

A comprehensive REST API for tracking legislation affecting Skilled Nursing Facilities (SNFs).

## Features

* **🔐 JWT Authentication** - Secure token-based authentication
* **📊 Bill Management** - Search, filter, and track legislative bills
* **🚨 Smart Alerts** - AI-powered change detection and notifications
* **📈 Dashboard Analytics** - Comprehensive statistics and trending analysis
* **⚡ High Performance** - Redis caching and rate limiting
* **📖 Full Documentation** - Complete API documentation with examples

## Authentication

Most endpoints require authentication using JWT Bearer tokens:

1. Register a new account: `POST /api/v1/auth/register`
2. Login to get tokens: `POST /api/v1/auth/login`
3. Use the access token in the Authorization header: `Authorization: Bearer <token>`
4. Refresh tokens when needed: `POST /api/v1/auth/refresh`

## Rate Limiting

API requests are limited to **{rate_limit_requests} requests per {rate_limit_window} seconds** per user/IP.
Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Request limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

## Caching

Responses are cached using Redis for improved performance:
- Bill lists: 5 minutes
- Bill details: 10 minutes
- Dashboard data: 3 minutes
- User alerts: 2 minutes

## Error Handling

The API uses standard HTTP status codes and returns error details in JSON format:

```json
{{
  "error": "Error type",
  "message": "Detailed error message",
  "details": {{}}
}}
```

## Support

For issues or questions:
- 📧 Email: support@snflegtracker.com
- 📖 Documentation: https://docs.snflegtracker.com
- 🐛 Issues: https://github.com/snflegtracker/api/issues
    """.format(
        rate_limit_requests=settings.rate_limit_requests,
        rate_limit_window=settings.rate_limit_window
    ),
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    lifespan=lifespan,
    contact={
        "name": "SNF Legislation Tracker Support",
        "email": "support@snflegtracker.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://snflegtracker.com/terms",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to 'https://pacadvocate.com' later
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Custom middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log requests and add timing headers"""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate timing
    process_time = time.time() - start_time

    # Add timing header
    response.headers["X-Process-Time"] = str(round(process_time, 4))

    # Log request (exclude health checks to reduce noise)
    if not request.url.path.startswith("/health"):
        logger.info(
            f"{request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Time: {process_time:.4f}s"
        )

    return response

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred" if not settings.debug else str(exc),
            "status_code": 500,
            "path": str(request.url.path),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Include routers
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(bills.router, prefix=settings.api_prefix)
app.include_router(alerts.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)

# Root endpoint
@app.get("/")
async def serve_dashboard():
    """Serve the dashboard HTML file at root"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Dashboard not found"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version
    }

# API info endpoint
@app.get("/info")
async def api_info():
    """Detailed API information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production",
        "features": {
            "authentication": "JWT with refresh tokens",
            "rate_limiting": f"{settings.rate_limit_requests} req/{settings.rate_limit_window}s",
            "caching": "Redis-based response caching",
            "documentation": "OpenAPI 3.0 with Swagger UI"
        },
        "endpoints": {
            "auth": f"{settings.api_prefix}/auth",
            "bills": f"{settings.api_prefix}/bills",
            "alerts": f"{settings.api_prefix}/alerts",
            "dashboard": f"{settings.api_prefix}/dashboard"
        },
        "documentation": {
            "swagger": settings.docs_url,
            "redoc": settings.redoc_url,
            "openapi": "/openapi.json"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Manual bill fetch endpoint
@app.post("/api/v1/fetch-bills")
async def trigger_bill_fetch():
    """Manually trigger fetching of new bills"""
    try:
        # For now, return a success message
        # TODO: Add actual bill fetching logic here
        return {"message": "Bill fetch endpoint ready - fetching logic needs to be added"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)