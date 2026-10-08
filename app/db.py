from dataclasses import dataclass
from typing import Any, Dict, Union

import pymysql

from .config import Settings


@dataclass
class MySQLSettings:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "video_gen_workbench"


def mysql_settings_from_app_settings(settings: Settings) -> MySQLSettings:
    return MySQLSettings(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
    )


def build_mysql_config(settings: Union[Settings, MySQLSettings]) -> Dict[str, Any]:
    return {
        "host": settings.mysql_host if hasattr(settings, "mysql_host") else settings.host,
        "port": settings.mysql_port if hasattr(settings, "mysql_port") else settings.port,
        "user": settings.mysql_user if hasattr(settings, "mysql_user") else settings.user,
        "password": settings.mysql_password if hasattr(settings, "mysql_password") else settings.password,
        "database": settings.mysql_database if hasattr(settings, "mysql_database") else settings.database,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 5,
        "read_timeout": 5,
        "write_timeout": 5,
    }


def build_mysql_server_config(settings: MySQLSettings) -> Dict[str, Any]:
    config = build_mysql_config(settings)
    config.pop("database", None)
    return config


def ensure_mysql_database(settings: MySQLSettings) -> None:
    connection = pymysql.connect(**build_mysql_server_config(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


def get_mysql_connection(settings: MySQLSettings):
    return pymysql.connect(**build_mysql_config(settings))


def check_mysql_connection(settings: MySQLSettings) -> Dict[str, Any]:
    connection = get_mysql_connection(settings)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            cursor.fetchone()
        return {
            "ok": True,
            "host": settings.host,
            "port": settings.port,
            "user": settings.user,
            "database": settings.database,
        }
    finally:
        connection.close()
