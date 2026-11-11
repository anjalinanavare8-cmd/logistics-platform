from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./logistics.db"
    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_MINUTES: int = 60
    RATE_LIMIT_PER_MIN: int = 120
    CACHE_TTL_SECONDS: int = 30
    model_config = {"env_file": ".env"}


settings = Settings()
