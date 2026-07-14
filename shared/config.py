from pathlib import Path
from pydantic_settings import BaseSettings,SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    database_url:str
    gemini_api_key:str
    apify_store:str
    apify_review:str
    threads_api_key:str

    model_config = SettingsConfigDict(
        env_file= BASE_DIR/".env",
        env_file_encoding="UTF-8",
        extra="ignore",
    )
settings = Settings() #type:ignore