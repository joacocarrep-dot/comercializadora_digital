from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@postgres:5432/comercializadora",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(
        default="your-secret-key-here",
        alias="SECRET_KEY",
    )
    env: str = Field(
        default="development",
        alias="ENV",
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Create a singleton instance
settings = Settings()
