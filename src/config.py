from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str

    REDIS_URL: str
    REDIS_HOST: str
    REDIS_PORT: int

    CELERY_URL: str

    DOMAIN: str

    COOKIE_SECURE: bool = False

    S3_ENDPOINT: str
    S3_PUBLIC_ENDPOINT: str
    S3_REGION: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

Config = Settings()
