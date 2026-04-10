from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    PROMETHEUS_URL: str = "http://localhost:9090"
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_BOT_TOKEN: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def checkpointer_url(self) -> str:
        """Convert async pg URL to standard pg URL for LangGraph checkpointer."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url


settings = Settings()