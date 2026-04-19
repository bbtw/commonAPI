from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CommonAPI"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"


settings = Settings()
