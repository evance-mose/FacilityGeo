from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "FacilityGeo"
    app_description: str = (
        "A spatial deployment monitoring system for health facilities in Malawi"
    )
    database_url: str = "sqlite:///./facilitygeo.db"
    coverage_radius_km: float = 8.0


settings = Settings()
