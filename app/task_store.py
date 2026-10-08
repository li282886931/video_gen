import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._default_state())

    def state(self) -> Dict[str, Any]:
        return self._read()

    def list_assets(self) -> List[Dict[str, Any]]:
        return self._read()["assets"]

    def create_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        state = self._read()
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
        state["assets"].append(asset)
        self._write(state)
        return asset

    def list_tasks(self) -> List[Dict[str, Any]]:
        return self._read()["tasks"]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        for task in self._read()["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        state = self._read()
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
        state["tasks"].append(task)
        self._write(state)
        return task

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        state = self._read()
        for task in state["tasks"]:
            if task["id"] == task_id:
                task.update(updates)
                task["updated_at"] = utc_now()
                self._write(state)
                return task
        raise KeyError(task_id)

    def create_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        state = self._read()
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
        state["orders"].append(order)
        self._write(state)
        return order

    def list_orders(self) -> List[Dict[str, Any]]:
        return self._read()["orders"]

    def membership(self) -> Dict[str, Any]:
        return self._read()["membership"]

    def admin_summary(self) -> Dict[str, Any]:
        state = self._read()
        return {
            "users": state["users"],
            "membership": state["membership"],
            "asset_count": len(state["assets"]),
            "task_count": len(state["tasks"]),
            "order_count": len(state["orders"]),
            "provider_configs": state["provider_configs"],
        }

    def upsert_provider_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        state = self._read()
        token = payload.get("api_token", "")
        config = {
            "kind": payload["kind"],
            "provider": payload["provider"],
            "enabled": bool(payload.get("enabled", False)),
            "model_name": payload.get("model_name", ""),
            "base_url": payload.get("base_url", ""),
            "has_token": bool(token or payload.get("has_token", False)),
        }
        configs = [
            item
            for item in state["provider_configs"]
            if not (item["kind"] == config["kind"] and item["provider"] == config["provider"])
        ]
        configs.append(config)
        state["provider_configs"] = configs
        self._write(state)
        return config

    def _read(self) -> Dict[str, Any]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return self._merge_defaults(data)

    def _write(self, state: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _merge_defaults(self, state: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._default_state()
        merged.update(deepcopy(state))
        for key, value in self._default_state().items():
            if isinstance(value, list):
                merged.setdefault(key, [])
            if isinstance(value, dict):
                nested = deepcopy(value)
                nested.update(merged.get(key, {}))
                merged[key] = nested
        return merged

    def _default_state(self) -> Dict[str, Any]:
        return {
            "assets": [],
            "tasks": [],
            "orders": [],
            "users": [{"id": "local-user", "name": "本地用户", "role": "admin"}],
            "membership": {
                "user_id": "local-user",
                "plan": "trial",
                "valid_until": "",
                "quota_total": 100,
                "quota_used": 0,
                "features": ["generation", "editing", "subtitles", "voiceover"],
            },
            "provider_configs": [
                {"kind": "video", "provider": "mock", "enabled": True, "model_name": "mock-video", "base_url": "", "has_token": False},
                {"kind": "image", "provider": "mock", "enabled": True, "model_name": "mock-image", "base_url": "", "has_token": False},
                {"kind": "tts", "provider": "mock", "enabled": True, "model_name": "mock-voice", "base_url": "", "has_token": False},
            ],
        }
