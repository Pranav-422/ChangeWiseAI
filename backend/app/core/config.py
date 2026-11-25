"""Settings from environment variables. Secrets are never defaulted, logged or returned by the API."""
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    environment: str
    log_level: str
    database_url: str
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    frontend_origins: tuple
    storage_bucket: str = "ecn-documents"
    max_upload_bytes: int = 4 * 1024 * 1024  # a Vercel function accepts a body of 4.5 MB
    pool_size: int = 5

    @property
    def jwt_issuer(self):
        return f"{self.supabase_url}/auth/v1"

    @property
    def production(self):
        return self.environment == "production"


@lru_cache
def get_settings():
    env = os.environ.get
    origins = tuple(o.strip().rstrip("/") for o in env("FRONTEND_ORIGIN", "").split(",") if o.strip())
    if "*" in origins:
        raise RuntimeError("FRONTEND_ORIGIN must list exact origins, not *.")
    return Settings(
        environment=env("ENVIRONMENT", "development"),
        log_level=env("LOG_LEVEL", "INFO").upper(),
        database_url=env("DATABASE_URL", ""),
        supabase_url=env("SUPABASE_URL", "").rstrip("/"),
        supabase_publishable_key=env("SUPABASE_PUBLISHABLE_KEY", ""),
        # New projects issue sb_secret_... keys; the legacy service_role key still works here.
        supabase_secret_key=env("SUPABASE_SECRET_KEY") or env("SUPABASE_SERVICE_ROLE_KEY", ""),
        frontend_origins=origins,
        pool_size=int(env("DB_POOL_SIZE", "5")),
    )
