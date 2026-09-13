"""Application configuration loaded from environment variables (.env).

No secrets are hardcoded; everything comes from the environment. See
`.env.example` for the full list of settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    db_host: str = "127.0.0.1"
    db_port: int = 3307
    db_user: str = "yatra"
    db_password: str = "yatra_dev_pw"
    db_name: str = "yatrapulse"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Dynamic ETA engine coefficients
    eta_historical_weight: float = 0.5
    eta_congestion_dwell: int = 8
    eta_downstream_factors: str = "0.6,0.4,0.25"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def downstream_factor_list(self) -> list[float]:
        return [float(f) for f in self.eta_downstream_factors.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
