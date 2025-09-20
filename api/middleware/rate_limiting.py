from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
from api.middleware.redis_client import redis_client
from api.config import settings
import time
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis"""

    def __init__(self, app, requests_per_minute: int = None, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window

    async def dispatch(self, request: StarletteRequest, call_next) -> Response:
        """Process request with rate limiting"""

        # Skip rate limiting for certain paths
        if self._should_skip_rate_limiting(request):
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_identifier(request)

        # Check rate limit
        is_allowed, rate_info = await redis_client.rate_limit_check(
            client_id,
            self.requests_per_minute,
            self.window_seconds
        )

        if not is_allowed:
            # Rate limit exceeded
            logger.warning(f"Rate limit exceeded for client {client_id}")

            headers = {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": str(rate_info.get("remaining", 0)),
                "X-RateLimit-Reset": str(rate_info.get("reset_time", 0)),
                "Retry-After": str(rate_info.get("retry_after", self.window_seconds))
            }

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_minute} requests per {self.window_seconds} seconds",
                    "retry_after": rate_info.get("retry_after", self.window_seconds)
                },
                headers=headers
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(rate_info.get("reset_time", 0))

        return response

    def _get_client_identifier(self, request: StarletteRequest) -> str:
        """Get client identifier for rate limiting"""

        # Try to get user ID from JWT token
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            try:
                from api.auth.jwt_handler import jwt_handler
                token = authorization.split(" ")[1]
                payload = jwt_handler.verify_token(token)
                if payload and payload.get("user_id"):
                    return f"user:{payload['user_id']}"
            except Exception:
                pass

        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get first IP from X-Forwarded-For header
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    def _should_skip_rate_limiting(self, request: StarletteRequest) -> bool:
        """Check if rate limiting should be skipped for this request"""

        # Skip for health checks and docs
        skip_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]

        path = request.url.path
        return any(path.startswith(skip_path) for skip_path in skip_paths)

# Rate limiting decorator for specific endpoints
def rate_limit(requests: int, window: int = 60):
    """Decorator for endpoint-specific rate limiting"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be implemented if we need per-endpoint rate limiting
            # For now, we use the middleware for global rate limiting
            return await func(*args, **kwargs)
        return wrapper
    return decorator