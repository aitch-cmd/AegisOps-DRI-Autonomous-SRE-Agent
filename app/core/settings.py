from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    PROMETHEUS_URL: str = "http://localhost:9090"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()