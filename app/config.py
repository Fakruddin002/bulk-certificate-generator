from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and settings."""

    APP_NAME: str = "Bulk Certificate Generator API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Base directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Database
    DATABASE_URL: str = "sqlite:///./certificates.db"

    # Storage for generated certificates and zip archives
    STORAGE_DIR: Path = BASE_DIR / "storage"
    GENERATED_CERTIFICATES_DIR: Path = BASE_DIR / "generated_certificates"
    CERTIFICATES_DIR: Path = GENERATED_CERTIFICATES_DIR
    ARCHIVES_DIR: Path = STORAGE_DIR / "archives"

    # Organization Defaults
    DEFAULT_ISSUER: str = "Global Certification Authority"
    DEFAULT_SIGNATORY_TITLE: str = "Authorized Director"

    # Base URL for verification links generated in certificates
    SERVER_HOST: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def init_directories(self) -> None:
        """Ensure all required storage directories exist."""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.GENERATED_CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
        self.CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
        self.ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.init_directories()
