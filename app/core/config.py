from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    alembic_database_url: str | None = None
    redis_url: str
    external_api_base_url: str = "http://91.199.149.128:18001"
    candidate_id: str = "4"


settings = Settings()