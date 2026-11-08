"""Configuration de l'application, lue depuis les variables d'environnement (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "API Atelier de couture"
    api_prefix: str = "/api/v1"

    # Base de données
    database_url: str

    # JWT
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Premier administrateur (script d'initialisation)
    admin_email: str | None = None
    admin_password: str | None = None
    admin_nom_complet: str = "Administrateur"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
