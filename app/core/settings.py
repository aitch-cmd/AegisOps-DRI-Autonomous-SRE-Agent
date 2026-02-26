from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    PROMETHEUS_URL: str = "http://localhost:9090"
    SLACK_WEBHOOK_URL: Optional[str] = None
    PAGERDUTY_ROUTING_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()