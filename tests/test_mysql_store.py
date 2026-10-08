import os
from uuid import uuid4

import pytest

from app.db import MySQLSettings
from app.mysql_store import MySQLTaskStore


def docker_mysql_settings() -> MySQLSettings:
    return MySQLSettings(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "123456789"),
        database=os.getenv("MYSQL_DATABASE", "video_gen_workbench"),
    )


def test_mysql_task_store_persists_business_records():
    store = MySQLTaskStore(docker_mysql_settings())
    suffix = uuid4().hex[:8]

    asset = store.create_asset(
        {
            "id": f"asset_test_{suffix}",
            "name": "mysql_clip.mp4",
            "type": "video",
            "source": "local",
            "path": "/tmp/mysql_clip.mp4",
            "metadata": {"tag": "mysql"},
        }
    )
    task = store.create_task(
        {
            "id": f"task_test_{suffix}",
            "title": "MySQL 任务",
            "module": "intelligent_editing",
            "asset_ids": [asset["id"]],
            "edit_profile": {"screen": {"fps": 30}},
        }
    )
    order = store.create_order(
        {
            "id": f"order_test_{suffix}",
            "user_id": "local-user",
            "plan": "pro",
            "amount": 199,
            "provider": "local",
        }
    )
    provider = store.upsert_provider_config(
        {"kind": "tts", "provider": f"mock_{suffix}", "enabled": True, "model_name": "voice-pro", "api_token": "secret"}
    )

    assert store.get_task(task["id"])["asset_ids"] == [asset["id"]]
    assert store.get_task(task["id"])["edit_profile"]["screen"]["fps"] == 30
    assert any(item["id"] == asset["id"] for item in store.list_assets())
    assert any(item["id"] == order["id"] for item in store.list_orders())
    assert provider["has_token"] is True
    assert "secret" not in str(store.state())


def test_mysql_task_store_marks_missing_connection_as_skipped():
    settings = MySQLSettings(host="127.0.0.1", port=1, user="root", password="bad", database="missing")
    with pytest.raises(Exception):
      MySQLTaskStore(settings).state()
