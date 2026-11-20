from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./clearwatt_dev.sqlite3"
    upload_dir: str = "./var/uploads"
    max_upload_mb: int = 12
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def origins(self) -> list[str]: return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

settings = Settings()
