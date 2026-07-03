from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ragbot"

    # OpenAI / models
    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # AI provider: "openai" (real), "gemini" (Google), or "fake" (offline, no cost).
    # "fake" is for local development/demo without any AI account.
    ai_provider: str = "openai"

    # Google / Gemini. Note: gemini-embedding-001 produces 3072-dim vectors, so set
    # EMBEDDING_DIM=3072 when ai_provider=gemini.
    google_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # Auth
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Seed admin
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"

    # CORS (comma-separated string in env)
    cors_origins: str = "http://localhost:3000"

    # RAG tuning
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 4

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
