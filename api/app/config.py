from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parent.parent  # .../api
_REPO_ROOT = _API_DIR.parent


class Settings(BaseSettings):
    # Absolute path so this resolves the same whether the process is started from the repo
    # root, from api/ (e.g. `cd api && uvicorn ...`), or via `mise run dev`/`start`. Render
    # deploys don't use this file at all — env vars are injected directly and always win.
    model_config = SettingsConfigDict(env_file=str(_REPO_ROOT / ".env"), extra="ignore")

    # Supabase Postgres (pgvector extension enabled). Example:
    # postgresql+psycopg://postgres:<password>@<project>.supabase.co:5432/postgres
    database_url: str = "postgresql+psycopg://guidebook:guidebook@localhost:5432/guidebook"

    # Cohere is the sole AI provider in this cloud/free-tier deployment profile.
    cohere_api_key: str = ""
    cohere_chat_model: str = "command-r-08-2024"
    cohere_embed_model: str = "embed-multilingual-v3.0"
    cohere_rerank_model: str = "rerank-multilingual-v3.0"
    cohere_timeout_seconds: float = 20.0

    embedding_dimensions: int = 1024

    # web/public/handbook so the Next.js app can also serve these PDFs as static assets
    # (Vercel Python functions only bundle files under this project's own root directory —
    # `api/` — so this path is only reachable outside Vercel, e.g. local dev or Render).
    handbook_dir: str = str(_REPO_ROOT / "web" / "public" / "handbook")
    # Inside api/ (not repo-root data/) so it's part of the Vercel function bundle: Stage 2
    # reads this file on every search request, not just at ingest time.
    lexicon_path: str = str(_API_DIR / "data" / "search_lexicon.yaml")

    admin_password: str = ""
    admin_session_secret: str = ""
    admin_session_hours: int = 8

    cors_allow_origins: str = "http://localhost:3000"

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password) and bool(self.admin_session_secret)

    @property
    def cohere_enabled(self) -> bool:
        return bool(self.cohere_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
