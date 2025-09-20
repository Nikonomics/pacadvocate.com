from functools import wraps
from typing import Any, Optional, Union, Callable
from datetime import timedelta
from api.middleware.redis_client import redis_client
from api.config import settings
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """Manage caching operations"""

    def __init__(self):
        self.default_expire = settings.cache_expire_seconds

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        return await redis_client.get(f"cache:{key}")

    async def set(
        self,
        key: str,
        value: Any,
        expire: Union[int, timedelta, None] = None
    ) -> bool:
        """Set cached value"""
        if expire is None:
            expire = self.default_expire
        return await redis_client.set(f"cache:{key}", value, expire)

    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        return await redis_client.delete(f"cache:{key}")

    async def clear_pattern(self, pattern: str) -> int:
        """Clear cache keys matching pattern"""
        try:
            client = await redis_client.get_client()
            keys = await client.keys(f"cache:{pattern}")
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {e}")
            return 0

    def make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        # Create a deterministic key from arguments
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())  # Sort for consistency
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()

# Global cache manager instance
cache = CacheManager()

def cached(
    expire: Union[int, timedelta, None] = None,
    key_prefix: str = "",
    skip_cache: bool = False
):
    """
    Caching decorator for functions

    Args:
        expire: Cache expiration time
        key_prefix: Prefix for cache key
        skip_cache: Skip caching (useful for debugging)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if skip_cache:
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{cache.make_key(*args, **kwargs)}"

            try:
                # Try to get from cache
                cached_result = await cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cached_result

                # Execute function and cache result
                result = await func(*args, **kwargs)

                # Cache the result
                await cache.set(cache_key, result, expire)
                logger.debug(f"Cached result for key: {cache_key}")

                return result

            except Exception as e:
                logger.error(f"Cache error for key {cache_key}: {e}")
                # On cache error, execute function normally
                return await func(*args, **kwargs)

        return wrapper
    return decorator

def cache_key_for_user(user_id: int, *args) -> str:
    """Generate cache key including user ID"""
    return f"user:{user_id}:{cache.make_key(*args)}"

def cache_key_for_bill(bill_id: int, *args) -> str:
    """Generate cache key for bill-related data"""
    return f"bill:{bill_id}:{cache.make_key(*args)}"

# Cache invalidation helpers
async def invalidate_user_cache(user_id: int):
    """Invalidate all cache entries for a user"""
    await cache.clear_pattern(f"user:{user_id}:*")

async def invalidate_bill_cache(bill_id: int):
    """Invalidate all cache entries for a bill"""
    await cache.clear_pattern(f"bill:{bill_id}:*")

async def invalidate_bills_cache():
    """Invalidate bills list cache"""
    await cache.clear_pattern("bills:*")

async def invalidate_dashboard_cache(user_id: int):
    """Invalidate dashboard cache for user"""
    await cache.clear_pattern(f"dashboard:{user_id}:*")

# Predefined cache configurations
CACHE_CONFIGS = {
    "bills_list": {"expire": 300, "key_prefix": "bills"},  # 5 minutes
    "bill_detail": {"expire": 600, "key_prefix": "bill"},  # 10 minutes
    "dashboard": {"expire": 180, "key_prefix": "dashboard"},  # 3 minutes
    "user_alerts": {"expire": 120, "key_prefix": "alerts"},  # 2 minutes
    "trending": {"expire": 600, "key_prefix": "trending"},  # 10 minutes
    "stats": {"expire": 300, "key_prefix": "stats"},  # 5 minutes
}

def get_cache_config(config_name: str) -> dict:
    """Get predefined cache configuration"""
    return CACHE_CONFIGS.get(config_name, {"expire": 300, "key_prefix": "default"})