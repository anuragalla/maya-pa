from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "LIVE150_"}

    # Service
    env: str = "dev"
    log_level: str = "INFO"
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # Database
    db_url_async: str = "postgresql+asyncpg://live150:live150dev@localhost:5432/live150"
    db_url_sync: str = "postgresql://live150:live150dev@localhost:5432/live150"

    # Auth
    jwt_issuer: str = "https://auth.live150.example"
    jwt_audience: str = "live150-agent"
    jwt_algorithm: str = "RS256"
    jwt_jwks_url: str | None = None
    jwt_public_key_pem: str | None = None
    jwt_jwks_cache_seconds: int = 600

    # Vertex AI
    gcp_project: str = "live150-dev"
    gcp_region: str = "us-central1"
    default_model: str = "gemini-3-flash"
    lite_model: str = "gemini-3-1-flash-lite"
    embedding_model: str = "text-embedding-005"

    # Live150 APIs
    api_base: str = "https://api.live150.example"
    notify_url: str = "https://notify.live150.example/send"
    service_api_token: str = ""

    # Live150 dev-route auth
    # In dev: impersonate users via /api/v1/login/developer/impersonate using the dev token.
    # In prod: a Live150 bearer token is already issued for the current user; pass it through.
    live150_dev_token: str = ""
    live150_bearer_token: str = ""
    live150_use_mock: bool = False
    live150_http_timeout_seconds: float = 30.0

    # OAuth
    oauth_redirect_base: str = "http://localhost:8000"

    # Crypto
    master_key: str = ""  # base64-encoded 32-byte key

    # Misc
    profile_ttl_minutes: int = 60
    rate_limit_chat_per_5min: int = 60
    rate_limit_reminders_per_min: int = 10


settings = Settings()
