from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    project_root: Path = BASE_PROJECT_ROOT
    storage_dir: Path = project_root / "storage"
    uploads_dir: Path = storage_dir / "uploads"
    extracted_dir: Path = storage_dir / "extracted"
    sqlite_path: Path = storage_dir / "main.db"
    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"
    vector_store_enabled: bool = True
    vector_store_dir: Path = storage_dir / "vector_store"
    vector_collection_name: str = "ufdr"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 16
    query_default_top_k: int = 5
    gemini_api_key: str | None = None
    gemini_model_name: str = "models/gemini-2.5-flash"
    gemini_temperature: float = 0.2
    gemini_top_p: float = 0.95
    gemini_max_output_tokens: int = 1024
    gemini_retry_attempts: int = 3
    gemini_vision_model_name: str = "models/gemini-2.5-flash-image"
    gemini_vision_temperature: float = 0.1
    gemini_vision_top_p: float = 0.9
    gemini_vision_max_output_tokens: int = 512

    model_config = SettingsConfigDict(
        env_file=str(BASE_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.extracted_dir.mkdir(parents=True, exist_ok=True)
    if settings.vector_store_enabled:
        settings.vector_store_dir.mkdir(parents=True, exist_ok=True)
    return settings
