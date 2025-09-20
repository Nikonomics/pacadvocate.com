import redis.asyncio as redis
import json
import pickle
from typing import Any, Optional, Union
from datetime import timedelta
from api.config import settings
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    """Async Redis client wrapper for caching and rate limiting"""

    def __init__(self):
        self.redis_url = settings.redis_url
        self._client = None

    async def get_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if self._client is None:
            try:
                self._client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=False  # We'll handle encoding manually
                )
                # Test connection
                await self._client.ping()
                logger.info("Redis client connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

        return self._client

    async def close(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value is None:
                return None

            # Try to decode as JSON first, fall back to pickle
            try:
                return json.loads(value.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return pickle.loads(value)
        except Exception as e:
            logger.error(f"Error getting key {key} from Redis: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: Union[int, timedelta, None] = None
    ) -> bool:
        """Set value in Redis"""
        try:
            client = await self.get_client()

            # Try to encode as JSON first, fall back to pickle
            try:
                encoded_value = json.dumps(value, default=str)
            except (TypeError, ValueError):
                encoded_value = pickle.dumps(value)

            result = await client.set(key, encoded_value)

            if expire is not None:
                if isinstance(expire, timedelta):
                    expire = int(expire.total_seconds())
                await client.expire(key, expire)

            return result
        except Exception as e:
            logger.error(f"Error setting key {key} in Redis: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            client = await self.get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting key {key} from Redis: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            client = await self.get_client()
            return await client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking existence of key {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter in Redis"""
        try:
            client = await self.get_client()
            return await client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {e}")
            return 0

    async def expire(self, key: str, expire: Union[int, timedelta]) -> bool:
        """Set expiration for key"""
        try:
            client = await self.get_client()
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())
            return await client.expire(key, expire)
        except Exception as e:
            logger.error(f"Error setting expiration for key {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get time to live for key"""
        try:
            client = await self.get_client()
            return await client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}")
            return -1

    # Rate limiting specific methods
    async def rate_limit_check(
        self,
        identifier: str,
        limit: int,
        window: int
    ) -> tuple[bool, dict]:
        """
        Check rate limit for identifier
        Returns: (is_allowed, info_dict)
        """
        try:
            client = await self.get_client()
            key = f"rate_limit:{identifier}"

            # Use sliding window log approach
            current_time = int(time.time())
            window_start = current_time - window

            pipe = client.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiration
            pipe.expire(key, window)

            results = await pipe.execute()
            current_requests = results[1]

            rate_limit_info = {
                "limit": limit,
                "remaining": max(0, limit - current_requests),
                "reset_time": current_time + window,
                "retry_after": window if current_requests >= limit else 0
            }

            is_allowed = current_requests < limit
            return is_allowed, rate_limit_info

        except Exception as e:
            logger.error(f"Error checking rate limit for {identifier}: {e}")
            # On error, allow the request
            return True, {"error": str(e)}

# Global Redis client instance
redis_client = RedisClient()

import time