import math
import os
from dataclasses import dataclass


def _positive_timeout_env(name: str, default: float, maximum: float | None = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value) or value <= 0 or (maximum is not None and value > maximum):
        return default
    return value


@dataclass
class Settings:
    app_name: str = os.getenv('APP_NAME', 'Tree Graph System')
    debug: bool = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    host: str = os.getenv('APP_HOST', '127.0.0.1')
    port: int = int(os.getenv('APP_PORT', '5002'))

    db_host: str = os.getenv('DB_HOST') or os.getenv('DB_MYSQL_HOST') or '183.69.145.186'
    db_port: int = int(os.getenv('DB_PORT', '33666'))
    db_user: str = os.getenv('DB_USER', 'hagongda')
    db_password: str = os.getenv('DB_PASSWORD', 'ha.G/o[tEst]n%gD*a')
    db_name: str = os.getenv('DB_NAME', 'r_d_test')
    db_charset: str = os.getenv('DB_CHARSET', 'utf8mb4')
    db_connect_timeout: float = _positive_timeout_env('DB_CONNECT_TIMEOUT', 5, maximum=31536000)
    db_read_timeout: float = _positive_timeout_env('DB_READ_TIMEOUT', 10)
    db_write_timeout: float = _positive_timeout_env('DB_WRITE_TIMEOUT', 10)


settings = Settings()
