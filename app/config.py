from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    db_name: str = "ghostnote"
    default_ttl_seconds: int = 3600
    cors_origins: List[str] = ["*"]

    model_config = {"env_file": ".env"}


settings = Settings()
