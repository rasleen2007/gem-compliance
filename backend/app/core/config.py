"""App configuration. Reads from environment / .env (see root .env.example)."""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    db_path: str = os.getenv("DB_PATH", "./data/ge_m_compliance.db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "./uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    allowed_extensions: set[str] = set(
        os.getenv("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,tiff,docx").split(",")
    )
    ocr_engine: str = os.getenv("OCR_ENGINE", "paddleocr")
    ocr_lang: str = os.getenv("OCR_LANG", "en")
    nlp_model: str = os.getenv("NLP_MODEL", "spacy_en_core_web_sm")
    llm_enabled: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()