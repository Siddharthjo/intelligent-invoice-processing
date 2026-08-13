from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg://invoice_app:invoice_app@localhost:5432/invoice_processing"

    max_upload_size_bytes: int = 20 * 1024 * 1024

    ocr_enabled: bool = True
    ocr_dpi: int = 300
    text_layer_min_chars_per_page: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
