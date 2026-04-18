from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "LIVE150_"}

    # Service
    env: str = "dev"
    log_level: str = "INFO"
    http_port: int = 8000

    # Database
    db_url_async: str = "postgresql+asyncpg://live150:live150dev@localhost:5432/live150"
    db_url_sync: str = "postgresql://live150:live150dev@localhost:5432/live150"

    # Live150 API
    api_base: str = "https://lifecloud.eng.sandbox.healthhustler.io"
    dev_token: str = ""
    notify_url: str = "http://localhost:8000/api/notifications/push"
    service_api_token: str = ""

    # Crypto
    master_key: str = ""  # base64-encoded 32-byte key

    # Misc
    profile_ttl_minutes: int = 60
    rate_limit_chat_per_5min: int = 60


settings = Settings()
