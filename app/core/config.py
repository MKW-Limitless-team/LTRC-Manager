from functools import lru_cache
from typing import List, Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    frontend_base_url: str = Field(default="http://localhost:5173", alias="FRONTEND_BASE_URL")
    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ALLOWED_ORIGINS",
    )

    discord_client_id: str = Field(default="", alias="DISCORD_CLIENT_ID")
    discord_client_secret: str = Field(default="", alias="DISCORD_CLIENT_SECRET")
    discord_redirect_uri: str = Field(default="", alias="DISCORD_REDIRECT_URI")

    session_secret: str = Field(default="development-session-secret", alias="SESSION_SECRET")
    session_cookie_name: str = Field(default="ltrc_session", alias="SESSION_COOKIE_NAME")
    session_max_age_seconds: int = Field(default=60 * 60 * 24 * 30, alias="SESSION_MAX_AGE_SECONDS")

    allowed_discord_user_ids: str = Field(default="", alias="ALLOWED_DISCORD_USER_IDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def allowed_user_ids(self) -> Set[str]:
        return {user_id.strip() for user_id in self.allowed_discord_user_ids.split(",") if user_id.strip()}

    def require_discord_oauth(self) -> None:
        missing = [
            name
            for name, value in [
                ("DISCORD_CLIENT_ID", self.discord_client_id),
                ("DISCORD_CLIENT_SECRET", self.discord_client_secret),
                ("DISCORD_REDIRECT_URI", self.discord_redirect_uri),
                ("SESSION_SECRET", self.session_secret),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required authentication settings: {', '.join(missing)}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
