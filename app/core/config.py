from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    webhook_secret: str | None = None

    @field_validator("webhook_secret")
    @classmethod
    def blank_secret_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def database_url(self) -> URL:
        # URL.create сам экранирует спецсимволы в пароле
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


settings = Settings()