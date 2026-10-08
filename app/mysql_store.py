import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .db import MySQLSettings, ensure_mysql_database, get_mysql_connection
from .task_store import utc_now


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def json_loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


class MySQLTaskStore:
    def __init__(self, settings: MySQLSettings):
        self.settings = settings
        ensure_mysql_database(settings)
        self.init_schema()
        self.seed_defaults()

    def state(self) -> Dict[str, Any]:
        return {
            "assets": self.list_assets(),
            "tasks": self.list_tasks(),
            "orders": self.list_orders(),
            "users": self.list_users(),
            "membership": self.membership(),
            "provider_configs": self.list_provider_configs(),
        }

    def list_assets(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM assets ORDER BY created_at DESC, id DESC")
                return [self._asset_from_row(row) for row in cursor.fetchall()]

    def create_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = utc_now()
        asset = {
            "id": payload.get("id") or f"asset_{uuid4().hex[:10]}",
            "name": payload["name"],
            "type": payload["type"],
            "source": payload.get("source", "local"),
            "path": payload.get("path", ""),
            "duration_seconds": payload.get("duration_seconds"),
            "resolution": payload.get("resolution"),
            "created_at": payload.get("created_at", now),
            "metadata": payload.get("metadata", {}),
        }
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO assets
                    (id, name, type, source, path, duration_seconds, resolution, created_at, metadata_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        asset["id"],
                        asset["name"],
                        asset["type"],
                        asset["source"],
                        asset["path"],
                        asset["duration_seconds"],
                        asset["resolution"],
                        asset["created_at"],
                        json_dumps(asset["metadata"]),
                    ),
                )
            connection.commit()
        return asset

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC, id DESC")
                return [self._task_from_row(row) for row in cursor.fetchall()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
                row = cursor.fetchone()
                return self._task_from_row(row) if row else None

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = utc_now()
        task = {
            "id": payload.get("id") or f"task_{uuid4().hex[:10]}",
            "title": payload["title"],
            "module": payload["module"],
            "status": payload.get("status", "pending"),
            "story_prompt": payload.get("story_prompt", ""),
            "asset_ids": payload.get("asset_ids", []),
            "edit_profile": payload.get("edit_profile", {}),
            "subtitle_cues": payload.get("subtitle_cues", []),
            "voiceover": payload.get("voiceover", {}),
            "progress": payload.get("progress", 0),
            "outputs": payload.get("outputs", {}),
            "error": payload.get("error", ""),
            "created_at": payload.get("created_at", now),
            "updated_at": payload.get("updated_at", now),
        }
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tasks
                    (id, title, module, status, story_prompt, asset_ids_json, edit_profile_json,
                     subtitle_cues_json, voiceover_json, progress, outputs_json, error, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        task["id"],
                        task["title"],
                        task["module"],
                        task["status"],
                        task["story_prompt"],
                        json_dumps(task["asset_ids"]),
                        json_dumps(task["edit_profile"]),
                        json_dumps(task["subtitle_cues"]),
                        json_dumps(task["voiceover"]),
                        task["progress"],
                        json_dumps(task["outputs"]),
                        task["error"],
                        task["created_at"],
                        task["updated_at"],
                    ),
                )
            connection.commit()
        return task

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_task(task_id)
        if not current:
            raise KeyError(task_id)
        current.update(updates)
        current["updated_at"] = utc_now()
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE tasks SET
                    title=%s, module=%s, status=%s, story_prompt=%s, asset_ids_json=%s,
                    edit_profile_json=%s, subtitle_cues_json=%s, voiceover_json=%s,
                    progress=%s, outputs_json=%s, error=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    (
                        current["title"],
                        current["module"],
                        current["status"],
                        current["story_prompt"],
                        json_dumps(current["asset_ids"]),
                        json_dumps(current["edit_profile"]),
                        json_dumps(current["subtitle_cues"]),
                        json_dumps(current["voiceover"]),
                        current["progress"],
                        json_dumps(current["outputs"]),
                        current["error"],
                        current["updated_at"],
                        task_id,
                    ),
                )
            connection.commit()
        return current

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        order = {
            "id": payload.get("id") or f"order_{uuid4().hex[:10]}",
            "user_id": payload.get("user_id", "local-user"),
            "plan": payload["plan"],
            "amount": payload.get("amount", 0),
            "currency": payload.get("currency", "CNY"),
            "status": payload.get("status", "created"),
            "provider": payload.get("provider", "local"),
            "created_at": payload.get("created_at", utc_now()),
        }
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO orders
                    (id, user_id, plan, amount, currency, status, provider, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order["id"],
                        order["user_id"],
                        order["plan"],
                        order["amount"],
                        order["currency"],
                        order["status"],
                        order["provider"],
                        order["created_at"],
                    ),
                )
            connection.commit()
        return order

    def list_orders(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM orders ORDER BY created_at DESC, id DESC")
                return [self._order_from_row(row) for row in cursor.fetchall()]

    def list_users(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, name, role FROM users ORDER BY id")
                return list(cursor.fetchall())

    def membership(self) -> Dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM memberships WHERE user_id = %s", ("local-user",))
                row = cursor.fetchone()
        if not row:
            return self._default_membership()
        return {
            "user_id": row["user_id"],
            "plan": row["plan"],
            "valid_until": row["valid_until"] or "",
            "quota_total": int(row["quota_total"]),
            "quota_used": int(row["quota_used"]),
            "features": json_loads(row["features_json"], []),
        }

    def admin_summary(self) -> Dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS count FROM assets")
                asset_count = cursor.fetchone()["count"]
                cursor.execute("SELECT COUNT(*) AS count FROM tasks")
                task_count = cursor.fetchone()["count"]
                cursor.execute("SELECT COUNT(*) AS count FROM orders")
                order_count = cursor.fetchone()["count"]
        return {
            "users": self.list_users(),
            "membership": self.membership(),
            "asset_count": int(asset_count),
            "task_count": int(task_count),
            "order_count": int(order_count),
            "provider_configs": self.list_provider_configs(),
        }

    def list_provider_configs(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM provider_configs ORDER BY kind, provider")
                return [self._provider_from_row(row) for row in cursor.fetchall()]

    def upsert_provider_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config = {
            "kind": payload["kind"],
            "provider": payload["provider"],
            "enabled": bool(payload.get("enabled", False)),
            "model_name": payload.get("model_name", ""),
            "base_url": payload.get("base_url", ""),
            "has_token": bool(payload.get("api_token") or payload.get("has_token", False)),
        }
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO provider_configs
                    (kind, provider, enabled, model_name, base_url, has_token)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    enabled=VALUES(enabled),
                    model_name=VALUES(model_name),
                    base_url=VALUES(base_url),
                    has_token=VALUES(has_token)
                    """,
                    (
                        config["kind"],
                        config["provider"],
                        int(config["enabled"]),
                        config["model_name"],
                        config["base_url"],
                        int(config["has_token"]),
                    ),
                )
            connection.commit()
        return config

    def init_schema(self) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                for statement in self._schema_statements():
                    cursor.execute(statement)
            connection.commit()

    def seed_defaults(self) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (id, name, role)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), role=VALUES(role)
                    """,
                    ("local-user", "本地用户", "admin"),
                )
                membership = self._default_membership()
                cursor.execute(
                    """
                    INSERT INTO memberships
                    (user_id, plan, valid_until, quota_total, quota_used, features_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE user_id=user_id
                    """,
                    (
                        membership["user_id"],
                        membership["plan"],
                        membership["valid_until"],
                        membership["quota_total"],
                        membership["quota_used"],
                        json_dumps(membership["features"]),
                    ),
                )
                for config in self._default_provider_configs():
                    cursor.execute(
                        """
                        INSERT INTO provider_configs
                        (kind, provider, enabled, model_name, base_url, has_token)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE kind=kind
                        """,
                        (
                            config["kind"],
                            config["provider"],
                            int(config["enabled"]),
                            config["model_name"],
                            config["base_url"],
                            int(config["has_token"]),
                        ),
                    )
            connection.commit()

    def _connection(self):
        return get_mysql_connection(self.settings)

    def _asset_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "source": row["source"],
            "path": row["path"],
            "duration_seconds": row["duration_seconds"],
            "resolution": row["resolution"],
            "created_at": row["created_at"],
            "metadata": json_loads(row["metadata_json"], {}),
        }

    def _task_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "module": row["module"],
            "status": row["status"],
            "story_prompt": row["story_prompt"],
            "asset_ids": json_loads(row["asset_ids_json"], []),
            "edit_profile": json_loads(row["edit_profile_json"], {}),
            "subtitle_cues": json_loads(row["subtitle_cues_json"], []),
            "voiceover": json_loads(row["voiceover_json"], {}),
            "progress": int(row["progress"]),
            "outputs": json_loads(row["outputs_json"], {}),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _order_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "plan": row["plan"],
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "status": row["status"],
            "provider": row["provider"],
            "created_at": row["created_at"],
        }

    def _provider_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "kind": row["kind"],
            "provider": row["provider"],
            "enabled": bool(row["enabled"]),
            "model_name": row["model_name"],
            "base_url": row["base_url"],
            "has_token": bool(row["has_token"]),
        }

    def _default_membership(self) -> Dict[str, Any]:
        return {
            "user_id": "local-user",
            "plan": "trial",
            "valid_until": "",
            "quota_total": 100,
            "quota_used": 0,
            "features": ["generation", "editing", "subtitles", "voiceover"],
        }

    def _default_provider_configs(self) -> List[Dict[str, Any]]:
        return [
            {"kind": "video", "provider": "mock", "enabled": True, "model_name": "mock-video", "base_url": "", "has_token": False},
            {"kind": "image", "provider": "mock", "enabled": True, "model_name": "mock-image", "base_url": "", "has_token": False},
            {"kind": "tts", "provider": "mock", "enabled": True, "model_name": "mock-voice", "base_url": "", "has_token": False},
        ]

    def _schema_statements(self) -> List[str]:
        return [
            """
            CREATE TABLE IF NOT EXISTS users (
              id VARCHAR(64) PRIMARY KEY,
              name VARCHAR(255) NOT NULL,
              role VARCHAR(64) NOT NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS memberships (
              user_id VARCHAR(64) PRIMARY KEY,
              plan VARCHAR(64) NOT NULL,
              valid_until VARCHAR(64) NOT NULL DEFAULT '',
              quota_total INT NOT NULL DEFAULT 0,
              quota_used INT NOT NULL DEFAULT 0,
              features_json JSON NOT NULL,
              CONSTRAINT fk_membership_user FOREIGN KEY (user_id) REFERENCES users(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS assets (
              id VARCHAR(64) PRIMARY KEY,
              name VARCHAR(255) NOT NULL,
              type VARCHAR(64) NOT NULL,
              source VARCHAR(64) NOT NULL,
              path TEXT NOT NULL,
              duration_seconds DOUBLE NULL,
              resolution VARCHAR(64) NULL,
              created_at VARCHAR(64) NOT NULL,
              metadata_json JSON NOT NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id VARCHAR(64) PRIMARY KEY,
              title VARCHAR(255) NOT NULL,
              module VARCHAR(128) NOT NULL,
              status VARCHAR(64) NOT NULL,
              story_prompt TEXT NOT NULL,
              asset_ids_json JSON NOT NULL,
              edit_profile_json JSON NOT NULL,
              subtitle_cues_json JSON NOT NULL,
              voiceover_json JSON NOT NULL,
              progress INT NOT NULL DEFAULT 0,
              outputs_json JSON NOT NULL,
              error TEXT NOT NULL,
              created_at VARCHAR(64) NOT NULL,
              updated_at VARCHAR(64) NOT NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
              id VARCHAR(64) PRIMARY KEY,
              user_id VARCHAR(64) NOT NULL,
              plan VARCHAR(64) NOT NULL,
              amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
              currency VARCHAR(16) NOT NULL,
              status VARCHAR(64) NOT NULL,
              provider VARCHAR(64) NOT NULL,
              created_at VARCHAR(64) NOT NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS provider_configs (
              kind VARCHAR(64) NOT NULL,
              provider VARCHAR(64) NOT NULL,
              enabled TINYINT(1) NOT NULL DEFAULT 0,
              model_name VARCHAR(255) NOT NULL DEFAULT '',
              base_url TEXT NOT NULL,
              has_token TINYINT(1) NOT NULL DEFAULT 0,
              PRIMARY KEY (kind, provider)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """,
        ]
