from __future__ import annotations

from typing import Optional

import pymysql

from ..config import settings


def get_mysql_connection() -> Optional[pymysql.connections.Connection]:
    try:
        return pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset=settings.db_charset,
            autocommit=True,
        )
    except pymysql.MySQLError:
        return None
