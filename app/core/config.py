from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import SecretStr
import logging

logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - [%(levelname)s] - %(name)s - "
                        "(%(filename)s).%(funcName)s(%(lineno)d) -%(message)s")


class Settings(BaseSettings):
    DEBUG: bool = False
    # Postgres
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # JWT
    SECRET_KEY: str = "CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 дней

    API_V1_STR: str = "/api/v1"

    # PDF
    TEMP_UPLOAD_DIR: str = "temp_uploads_pdf"
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5 MB

    # LLM
    llm_provider: str = "google"
    llm_model_name: str = "gemini-2.5-flash-preview-05-20"
    assistant_api_key: SecretStr = ""
    gemini_api_key: SecretStr = ""
    temperature: float = 0.25
    top_p: float = 0.9
    openai_proxy: str | None = None

    # Yandex
    YC_API_KEY: SecretStr
    YC_FOLDER_ID: SecretStr
    YC_MODEL_VERSION: str = "latest"

    # Google Sheets
    GSHEETS_CREDS_PATH: str = "creds.json"          # путь к creds.json
    GSHEETS_SHEET_ID: str                               # ID таблицы
    GSHEETS_FIRST_TAB: str = "Sheet1"                   # имя вкладки
    ADMIN_SYNC_TOKEN: str                               # секрет

    # API
    APP_URL: str = "http://app:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
