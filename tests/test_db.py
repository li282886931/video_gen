from unittest.mock import MagicMock, Mock

from fastapi.testclient import TestClient

from app.api import app
from app.config import Settings
from app.db import MySQLSettings, build_mysql_config, ensure_mysql_database, check_mysql_connection


def test_build_mysql_config_uses_settings_values():
    settings = Settings(
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="root",
        mysql_password="123456789",
        mysql_database="video_gen_workbench",
    )

    config = build_mysql_config(settings)

    assert config["host"] == "127.0.0.1"
    assert config["port"] == 3306
    assert config["user"] == "root"
    assert config["password"] == "123456789"
    assert config["database"] == "video_gen_workbench"
    assert config["charset"] == "utf8mb4"


def test_check_mysql_connection_masks_password(monkeypatch):
    cursor = Mock()
    cursor.fetchone.return_value = {"ok": 1}
    connection = Mock()
    connection.cursor.return_value = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connect = Mock(return_value=connection)

    monkeypatch.setattr("app.db.pymysql.connect", connect)

    result = check_mysql_connection(
        MySQLSettings(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="123456789",
            database="video_gen_workbench",
        )
    )

    assert result["ok"] is True
    assert result["database"] == "video_gen_workbench"
    assert "123456789" not in str(result)
    connect.assert_called_once()
    connection.close.assert_called_once()


def test_ensure_mysql_database_creates_database(monkeypatch):
    cursor = Mock()
    connection = Mock()
    connection.cursor.return_value = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connect = Mock(return_value=connection)
    monkeypatch.setattr("app.db.pymysql.connect", connect)

    ensure_mysql_database(
        MySQLSettings(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="123456789",
            database="video_gen_workbench",
        )
    )

    executed_sql = cursor.execute.call_args[0][0]
    assert "CREATE DATABASE IF NOT EXISTS `video_gen_workbench`" in executed_sql
    connect.assert_called_once()
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_db_health_endpoint_reports_configured_database(monkeypatch):
    monkeypatch.setattr(
        "app.api.check_mysql_connection",
        lambda mysql_settings: {"ok": True, "host": mysql_settings.host, "database": mysql_settings.database},
    )

    client = TestClient(app)
    resp = client.get("/api/db/health")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["database"] == "video_gen_workbench"
