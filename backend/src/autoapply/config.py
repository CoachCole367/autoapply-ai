from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./autoapply.db"
    api_token: str = Field(min_length=24)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    data_dir: str = "data"


@lru_cache
def config():
    return Config()
