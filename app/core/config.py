"""
Plotra Platform - Configuration Loader
Loads settings from config.yaml with environment variable override support
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "Plotra Platform"
    version: str = "1.0.0"
    debug: bool = False
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

    @property
    def async_url(self) -> str:
        if self.name == "sqlite":
            # Use an absolute path to sqlite.db in the root directory
            base_dir = Path(__file__).parent.parent.parent
            db_path = base_dir / f"{self.name}.db"
            return f"sqlite+aiosqlite:///{db_path.absolute()}"
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"


class PostGISConfig(BaseModel):
    enabled: bool = True
    srid: int = 4326


class SatelliteConfig(BaseModel):
    provider: str = "sentinel_hub"
    api_key: str = ""
    base_url: str = "https://services.sentinel-hub.com"
    simulation_mode: bool = True
    ndvi_threshold: float = 0.65
    deforestation_baseline_year: int = 2020
    risk_thresholds: Dict[str, float] = Field(default_factory=lambda: {
        "high": 70.0,
        "medium": 30.0
    })


class EUDRConfig(BaseModel):
    compliance_status: str = "Under Review"
    certificate_validity_days: int = 365
    dds_version: str = "1.0"
    compliance_thresholds: Dict[str, float] = Field(default_factory=lambda: {
        "compliant": 90.0,
        "under_review": 70.0,
        "requires_action": 50.0
    })
    compliance_scoring_weights: Dict[str, int] = Field(default_factory=lambda: {
        "deforestation_free": 30,
        "legal_ownership": 25,
        "traceability_verified": 25,
        "documents_complete": 10,
        "satellite_analysis": 10
    })


class GeospatialConfig(BaseModel):
    gps_accuracy_threshold_meters: float = 10
    min_polygon_area_hectares: float = 0.1
    max_farm_polygons_per_farmer: int = 10


class StorageConfig(BaseModel):
    documents_path: str = "./uploads/documents"
    certificates_path: str = "./uploads/certificates"
    max_file_size_mb: int = 50


class CORSConfig(BaseModel):
    allowed_origins: list = [
        # Production domains (HTTPS only)
        "https://dev.plotra.eu",
        "https://plotra.eu",
        "https://www.plotra.eu",
    ]


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class AuthConfig(BaseModel):
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    password_reset_token_expiry_hours: int = 24
    # Polygon capture API key (prototype/URS)
    polygon_api_key: str = "plotra-prototype-key-2026"


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


class EmailConfig(BaseModel):
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@plotra.africa"
    from_name: str = "Plotra Platform"
    use_tls: bool = True
    debug_mode: bool = False


class Settings(BaseModel):
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
    payments: PaymentsConfig = Field(default_factory=PaymentsConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)


def load_config(config_path: Optional[str] = None) -> Settings:
    """
    Load configuration from YAML file with environment variable override support.

    Args:
        config_path: Path to config.yaml file. Defaults to project root config.yaml

    Returns:
        Settings object with loaded configuration
    """
    if config_path is None:
        config_path = os.environ.get(
            "PLOTRA_CONFIG_PATH",
            str(Path(__file__).parent.parent.parent / "config.yaml")
        )

    config_data: Dict[str, Any] = {}

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}

    # Apply environment variable overrides
    env_overrides = {
        "PLOTRA_SECRET_KEY": ("app", "secret_key"),
        "PLOTRA_DB_HOST": ("database", "host"),
        "PLOTRA_DB_PORT": ("database", "port"),
        "PLOTRA_DB_USER": ("database", "username"),
        "PLOTRA_DB_PASSWORD": ("database", "password"),
        "PLOTRA_DB_NAME": ("database", "name"),
        "SENTINEL_API_KEY": ("satellite", "api_key"),
        "PLOTRA_DEBUG": ("app", "debug"),
    }

    for env_var, (section, key) in env_overrides.items():
        value = os.environ.get(env_var)
        if value is not None:
            if section not in config_data:
                config_data[section] = {}

            # Type conversion for specific fields
            if key == "port":
                value = int(value)
            elif key == "debug":
                value = value.lower() in ("true", "1", "yes")

            config_data[section][key] = value

    return Settings(**config_data)


def save_config(settings: Settings, config_path: Optional[str] = None) -> None:
    """
    Save configuration to YAML file.

    Args:
        settings: Settings object to save
        config_path: Path to config.yaml file. Defaults to project root config.yaml
    """
    if config_path is None:
        config_path = os.environ.get(
            "PLOTRA_CONFIG_PATH",
            str(Path(__file__).parent.parent.parent / "config.yaml")
        )

    # Convert settings to dict
    config_data = settings.model_dump()

    # Save to file
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)


# Global settings instance
settings = load_config()
