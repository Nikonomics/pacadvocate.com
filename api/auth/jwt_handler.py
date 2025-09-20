from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from api.config import settings
from models.legislation import User
import redis
import json

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis client for token blacklisting
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

class JWTHandler:
    """Handle JWT token creation, verification, and management"""

    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create an access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow()
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        """Create a refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "iat": datetime.utcnow()
        })

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        # Store refresh token in Redis with expiration
        redis_key = f"refresh_token:{data['user_id']}"
        token_data = {
            "token": encoded_jwt,
            "user_id": data["user_id"],
            "email": data["email"],
            "created_at": datetime.utcnow().isoformat()
        }
        redis_client.setex(
            redis_key,
            timedelta(days=self.refresh_token_expire_days).total_seconds(),
            json.dumps(token_data)
        )

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode a token"""
        try:
            # Check if token is blacklisted
            if self.is_token_blacklisted(token):
                return None

            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    def verify_refresh_token(self, token: str) -> Optional[dict]:
        """Verify a refresh token and check if it exists in Redis"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            if payload.get("type") != "refresh":
                return None

            # Check if refresh token exists in Redis
            redis_key = f"refresh_token:{payload['user_id']}"
            stored_token_data = redis_client.get(redis_key)

            if not stored_token_data:
                return None

            stored_data = json.loads(stored_token_data)
            if stored_data["token"] != token:
                return None

            return payload
        except JWTError:
            return None

    def blacklist_token(self, token: str):
        """Add token to blacklist"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            exp_timestamp = payload.get("exp")

            if exp_timestamp:
                # Calculate remaining time until expiration
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                remaining_time = exp_datetime - datetime.utcnow()

                if remaining_time.total_seconds() > 0:
                    redis_client.setex(
                        f"blacklisted_token:{token}",
                        int(remaining_time.total_seconds()),
                        "blacklisted"
                    )
        except JWTError:
            pass

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        return redis_client.exists(f"blacklisted_token:{token}")

    def revoke_refresh_token(self, user_id: int):
        """Revoke refresh token for a user"""
        redis_key = f"refresh_token:{user_id}"
        redis_client.delete(redis_key)

    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user"""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_tokens_for_user(self, user: User) -> dict:
        """Create both access and refresh tokens for a user"""
        token_data = {
            "user_id": user.id,
            "email": user.email,
            "sub": str(user.id)
        }

        access_token = self.create_access_token(data=token_data)
        refresh_token = self.create_refresh_token(data=token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

# Global JWT handler instance
jwt_handler = JWTHandler()