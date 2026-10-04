from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', case_sensitive=False)

    database_url: str | None = None
    database_direct_url: str | None = None
    openai_embeddings_api_key: str | None = None
    embeddings_provider: str = 'openai'
    embeddings_model: str = 'text-embedding-3-small'
    embedding_dimensions: int = 1536
    llm_provider: str = 'openai'
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = 'gpt-4o-mini'
    llm_api_key: str | None = None
    app_session_secret: str | None = None
    app_cookie_secure: bool = True
    app_cookie_name: str = 'docusleuth_session'
    cors_origins: str = 'http://localhost:3000'
    ocr_languages: str = 'eng'
    max_file_size: int = 25 * 1024 * 1024
    max_files_per_workspace: int = 20
    uploads_per_hour: int = 40
    max_upload_batch_bytes: int = 200 * 1024 * 1024
    max_tokens_per_answer: int = 1200
    questions_per_hour: int = 60
    max_conflict_candidates: int = 200
    manus_api_url: str | None = None
    manus_api_key: str | None = None
    manus_project_id: str | None = None
    manus_jwt_secret: str | None = None
    manus_oauth_api_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
