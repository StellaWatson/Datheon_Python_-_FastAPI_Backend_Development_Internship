from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = "sqlite+aiosqlite:///./bookstore.db"

    # Rate limiting (requests per window, per client IP)
    RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT: int = 5
    API_RATE_LIMIT: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Background jobs
    WEBHOOK_URL: str | None = None
    WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    WEBHOOK_MAX_RETRIES: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()