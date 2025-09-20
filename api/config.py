from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    model_config = {'extra': 'ignore', 'env_file': '.env', 'case_sensitive': False}

    # Basic app settings
    app_name: str = "SNF Legislation Tracker API"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./snflegtracker.db")

    # JWT Settings
    secret_key: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Redis settings
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache_expire_seconds: int = 300  # 5 minutes default cache

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # API settings
    api_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"

    # OpenAI (for AI analysis)
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")

    # Email settings (for notifications)
    smtp_server: str = os.getenv("SMTP_SERVER", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")


settings = Settings()