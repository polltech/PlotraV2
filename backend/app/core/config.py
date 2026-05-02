"""
Plotra Platform - Configuration Loader
Loads settings from config.yaml with environment variable override support
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)
logger.info(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}")
logger.info(f"Database name env: {os.environ.get('PLOTRA_DATABASE__NAME', 'not set')}")


class AppConfig(BaseModel):
    name: str = "Plotra Platform"
    version: str = "1.0.0"
    debug: bool = False
    env: str = "development"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    frontend_base_url: str = "https://dev.plotra.eu"


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    name: str = "sqlite"
    pool_size: int = 10
    max_overflow: int = 20
    async_mode: bool = True

    @property
    def async_url(self) -> str:
        if self.name == "sqlite":
            # Use an absolute path to sqlite.db in the backend directory
            base_dir = Path(__file__).parent.parent.parent
            db_path = base_dir / f"{self.name}.db"
            return f"sqlite+aiosqlite:///{db_path.absolute()}"
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0


class PostGISConfig(BaseModel):
    enabled: bool = True
    srid: int = 4326


class SatelliteConfig(BaseModel):
    provider: str = "sentinel_hub"
    api_key: str = ""
    base_url: str = "https://services.sentinel-hub.com"
    simulation_mode: bool = True
    ndvi_threshold: float = 0.65
    deforestation_baseline_year: int = 2014
    biomass_threshold: float = 100.0


class EUDRConfig(BaseModel):
    compliance_status: str = "Under Review"
    certificate_validity_days: int = 365
    dds_version: str = "1.0"
    portal_url: str = "https://eudr-portal.example.com"


class GeospatialConfig(BaseModel):
    gps_accuracy_threshold_meters: float = 10
    min_polygon_area_hectares: float = 0.1
    max_farm_polygons_per_farmer: int = 10
    parent_child_validation: bool = True
    boundary_overlap_tolerance: float = 0.01


class StorageConfig(BaseModel):
    documents_path: str = "./uploads/documents"
    certificates_path: str = "./uploads/certificates"
    photos_path: str = "./uploads/photos"
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "af-south-1"


class CeleryConfig(BaseModel):
    broker_url: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"


class CORSConfig(BaseModel):
    allowed_origins: list = [
        "https://dev.plotra.eu",
        "https://plotra.eu",
        "https://www.plotra.eu",
    ]


class AuthConfig(BaseModel):
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    password_reset_token_expiry_hours: int = 24


class EmailConfig(BaseModel):
    """Email service configuration"""
    resend_api_key: str = ""
    from_email: str = "plotra@vegrid.co.ke"
    from_name: str = "Plotra Platform"
    debug_mode: bool = False


class PaymentsConfig(BaseModel):
    enabled: bool = False
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    escrow_enabled: bool = True


class VerificationConfig(BaseModel):
    require_all_fields: bool = False
    auto_submit_eudr: bool = False
    alert_threshold_days: int = 30


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "logs/plotra.log"
    audit_enabled: bool = True


class MobileConfig(BaseModel):
    # Set PLOTRA_MOBILE__API_KEY in env to override the default
    api_key: str = "plotra-prototype-key-2026"
    # Max requests per IP per minute on mobile endpoints
    rate_limit_per_minute: int = 60


class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    postgis: PostGISConfig = Field(default_factory=PostGISConfig)
    satellite: SatelliteConfig = Field(default_factory=SatelliteConfig)
    eudr: EUDRConfig = Field(default_factory=EUDRConfig)
    geospatial: GeospatialConfig = Field(default_factory=GeospatialConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    mobile: MobileConfig = Field(default_factory=MobileConfig)
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)

    class Config:
        env_prefix = "PLOTRA_"
        env_nested_delimiter = "__"

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings, **kwargs):
        # Env vars take priority over init kwargs (YAML data)
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)

    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None) -> "Settings":
        """Load settings from YAML file. Env vars take priority over YAML."""
        if config_path is None:
            config_path = os.environ.get(
                "PLOTRA_CONFIG_PATH",
                str(Path(__file__).parent.parent / "config.yaml")
            )

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            return cls(**config_data)

        return cls()


def load_config(config_path: Optional[str] = None) -> Settings:
    """
    Load configuration from YAML file with environment variable override support.
    """
    return Settings.from_yaml(config_path)


# Global settings instance
settings = load_config()
