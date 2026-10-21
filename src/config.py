from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str

    REDIS_URL: str
    REDIS_HOST: str
    REDIS_PORT: int

    DOMAIN: str

    COOKIE_SECURE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

Config = Settings()
