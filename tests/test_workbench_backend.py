from pathlib import Path

from fastapi.testclient import TestClient

from app.api import app, set_workbench_store
from app.task_store import TaskStore
from app.video_ops import VideoOperationPlanner, build_srt


def auth_headers(client: TestClient) -> dict:
    username = "local-user"
    password = "local-password"
    client.post("/api/auth/register", json={"username": username, "password": password, "display_name": "本地用户"})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_task_store_persists_assets_tasks_and_orders(tmp_path):
    store = TaskStore(tmp_path / "workbench.json")

    asset = store.create_asset(
        {
            "name": "launch.mp4",
            "type": "video",
            "source": "local",
            "path": "/tmp/launch.mp4",
            "duration_seconds": 18,
            "resolution": "1080x1920",
        }
    )
    task = store.create_task(
        {
            "title": "新品发布短片",
            "module": "intelligent_editing",
            "story_prompt": "城市夜景中的新品发布会",
            "asset_ids": [asset["id"]],
        }
    )
    order = store.create_order({"user_id": "local-user", "plan": "pro", "amount": 199})

    reloaded = TaskStore(tmp_path / "workbench.json")

    assert reloaded.list_assets()[0]["id"] == asset["id"]
    assert reloaded.get_task(task["id"])["status"] == "pending"
    assert reloaded.list_orders()[0]["id"] == order["id"]
    assert reloaded.membership()["plan"] == "trial"


def test_build_srt_formats_subtitle_cues():
    srt = build_srt(
        [
            {"start_ms": 0, "end_ms": 1250, "text": "第一句"},
            {"start_ms": 1250, "end_ms": 3500, "text": "第二句"},
        ]
    )

    assert "1\n00:00:00,000 --> 00:00:01,250\n第一句" in srt
    assert "2\n00:00:01,250 --> 00:00:03,500\n第二句" in srt


def test_video_operation_planner_builds_watermark_region_and_export_commands(tmp_path):
    planner = VideoOperationPlanner(ffmpeg_bin="ffmpeg")
    output = tmp_path / "out.mp4"
    command = planner.build_processing_command(
        input_path="/tmp/in.mp4",
        output_path=output,
        operations={
            "crop": {"width": 720, "height": 1280, "x": 0, "y": 0},
            "speed": 1.25,
            "mirror": True,
            "mute": True,
            "watermark": {"mode": "blur", "x": 20, "y": 30, "width": 160, "height": 80},
            "export": {"resolution": "720x1280", "fps": 30, "bitrate": "2500k"},
        },
    )

    joined = " ".join(command)
    assert command[:2] == ["ffmpeg", "-y"]
    assert "crop=720:1280:0:0" in joined
    assert "setpts=0.8*PTS" in joined
    assert "hflip" in joined
    assert "boxblur" in joined
    assert "-an" in command
    assert "-r" in command and "30" in command
    assert str(output) == command[-1]


def test_workbench_api_creates_task_and_exports_srt(tmp_path):
    set_workbench_store(TaskStore(tmp_path / "workbench.json"))
    client = TestClient(app)
    headers = auth_headers(client)

    asset_resp = client.post(
        "/api/assets",
        json={"name": "clip.mp4", "type": "video", "source": "local", "path": "/tmp/clip.mp4"},
        headers=headers,
    )
    assert asset_resp.status_code == 200
    asset_id = asset_resp.json()["id"]

    task_resp = client.post(
        "/api/tasks",
        json={
            "title": "混剪任务",
            "module": "intelligent_editing",
            "story_prompt": "品牌发布会",
            "asset_ids": [asset_id],
            "subtitle_cues": [{"start_ms": 0, "end_ms": 1000, "text": "开场"}],
        },
        headers=headers,
    )
    assert task_resp.status_code == 200
    assert task_resp.json()["status"] == "pending"

    state_resp = client.get("/api/workbench/state", headers=headers)
    assert state_resp.status_code == 200
    assert state_resp.json()["tasks"][0]["title"] == "混剪任务"

    srt_resp = client.post(
        "/api/subtitles/srt",
        json={"cues": [{"start_ms": 0, "end_ms": 1000, "text": "开场"}]},
        headers=headers,
    )
    assert srt_resp.status_code == 200
    assert "00:00:00,000 --> 00:00:01,000" in srt_resp.json()["srt"]


def test_admin_provider_config_masks_tokens(tmp_path):
    set_workbench_store(TaskStore(tmp_path / "workbench.json"))
    client = TestClient(app)
    headers = auth_headers(client)

    resp = client.put(
        "/api/admin/provider-config",
        json={"kind": "tts", "provider": "mock", "enabled": True, "model_name": "voice-pro", "api_token": "secret"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["has_token"] is True
    assert "secret" not in resp.text


def test_backend_does_not_serve_frontend_static_files():
    client = TestClient(app)

    assert not Path("app/chat_ui.html").exists()
    assert not Path("app/static_chat_ui.js").exists()
    assert not Path("app/static_chat_ui.css").exists()
    assert client.get("/").status_code == 404
    assert client.get("/static_chat_ui.js").status_code == 404
    assert client.get("/static_chat_ui.css").status_code == 404
