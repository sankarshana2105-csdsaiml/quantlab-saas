import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    pass


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    environment: str
    cors_origins: tuple[str, ...]
    allowed_hosts: tuple[str, ...]
    max_dataset_bars: int
    jwt_expire_minutes: int

    @classmethod
    def from_environment(cls) -> "Settings":
        environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        if environment not in {"development", "test", "production"}:
            raise ConfigurationError("ENVIRONMENT must be development, test, or production")
        origins = tuple(value.strip().rstrip("/") for value in os.getenv("CORS_ORIGINS", "").split(",") if value.strip())
        hosts = tuple(value.strip() for value in os.getenv("ALLOWED_HOSTS", "").split(",") if value.strip())
        settings = cls(
            environment, origins, hosts,
            _positive_int("MAX_DATASET_BARS", 100_000),
            _positive_int("JWT_EXPIRE_MINUTES", 30),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if any(origin == "*" or urlparse(origin).scheme not in {"http", "https"} or not urlparse(origin).netloc for origin in self.cors_origins):
            raise ConfigurationError("CORS_ORIGINS must contain explicit http(s) origins")
        if self.environment == "production" and "*" in self.allowed_hosts:
            raise ConfigurationError("ALLOWED_HOSTS cannot contain a wildcard in production")
        if self.environment == "production":
            if len(os.getenv("JWT_SECRET", "")) < 32:
                raise ConfigurationError("JWT_SECRET must contain at least 32 characters in production")
            database_url = os.getenv("DATABASE_URL", "")
            if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ConfigurationError("DATABASE_URL must use PostgreSQL in production")
            if not self.cors_origins:
                raise ConfigurationError("CORS_ORIGINS is required in production")
