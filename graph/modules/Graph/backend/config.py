import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = os.getenv('APP_NAME', 'Tree Graph System')
    debug: bool = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    host: str = os.getenv('APP_HOST', '127.0.0.1')
    port: int = int(os.getenv('APP_PORT', '5002'))

    db_host: str = os.getenv('DB_HOST', '183.69.138.62')
    db_port: int = int(os.getenv('DB_PORT', '33666'))
    db_user: str = os.getenv('DB_USER', 'hagongda')
    db_password: str = os.getenv('DB_PASSWORD', 'ha.G/o[tEst]n%gD*a')
    db_name: str = os.getenv('DB_NAME', 'r_d_test')
    db_charset: str = os.getenv('DB_CHARSET', 'utf8mb4')


settings = Settings()
