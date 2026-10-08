import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth_store import MySQLAuthStore
from .config import get_settings
from .db import check_mysql_connection, mysql_settings_from_app_settings
from .harness import Harness
from .mysql_store import MySQLTaskStore
from .providers import MockVoiceoverProvider
from .task_store import TaskStore
from .video_ops import build_srt


app = FastAPI(title="VideoGen API")
# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()
harness = Harness(settings)


def create_default_workbench_store():
    try:
        return MySQLTaskStore(mysql_settings_from_app_settings(settings))
    except Exception:
        return TaskStore(Path(settings.output_dir).expanduser() / "workbench_state.json")


workbench_store = create_default_workbench_store()


def create_default_auth_store():
    try:
        return MySQLAuthStore(mysql_settings_from_app_settings(settings))
    except Exception:
        return None


auth_store = create_default_auth_store()


def set_workbench_store(store: TaskStore) -> None:
    global workbench_store
    workbench_store = store


def set_auth_store(store) -> None:
    global auth_store
    auth_store = store


def model_payload(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    reply: str


class PlanRequest(BaseModel):
    story_prompt: str
    shot_count: Optional[int] = None


class ShotOut(BaseModel):
    id: str
    prompt: str
    duration_seconds: int
    camera: Optional[str] = None


class AssetRequest(BaseModel):
    name: str
    type: str
    source: str = "local"
    path: str = ""
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None
    metadata: Dict[str, Any] = {}


class SubtitleCueIn(BaseModel):
    start_ms: int
    end_ms: int
    text: str


class TaskRequest(BaseModel):
    title: str
    module: str
    story_prompt: str = ""
    asset_ids: List[str] = []
    edit_profile: Dict[str, Any] = {}
    subtitle_cues: List[SubtitleCueIn] = []
    voiceover: Dict[str, Any] = {}


class SrtRequest(BaseModel):
    cues: List[SubtitleCueIn]


class VoiceoverRequest(BaseModel):
    text: str
    voice: str = "standard"
    speed: float = 1.0
    pitch: float = 1.0
    language: str = "zh-CN"


class OrderRequest(BaseModel):
    user_id: str = "local-user"
    plan: str
    amount: float = 0
    currency: str = "CNY"
    provider: str = "local"


class ProviderConfigRequest(BaseModel):
    kind: str
    provider: str
    enabled: bool = True
    model_name: str = ""
    base_url: str = ""
    api_token: str = ""


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class WalletChangeRequest(BaseModel):
    amount: float
    note: str = ""


def require_account(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    if auth_store is None:
        raise HTTPException(status_code=503, detail="Authentication store is not configured")
    token = authorization.removeprefix("Bearer ").strip()
    account = auth_store.account_from_token(token)
    if not account:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return account


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must contain at least 8 characters")
    if auth_store is None:
        raise HTTPException(status_code=503, detail="Authentication store is not configured")
    try:
        account = auth_store.register(req.username, req.password, req.display_name)
        return {"user": account}
    except ValueError as e:
        if str(e) == "username_exists":
            raise HTTPException(status_code=409, detail="Username already exists")
        raise


@app.post("/api/auth/login")
def login(req: LoginRequest):
    if auth_store is None:
        raise HTTPException(status_code=503, detail="Authentication store is not configured")
    try:
        return auth_store.login(req.username, req.password)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Invalid username or password")


@app.get("/api/auth/me")
def me(account: Dict[str, Any] = Depends(require_account)):
    return account


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    messages = []
    if req.history:
        # expect history as list of {role, content}
        messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    try:
        msg = harness.chat(messages)
        return ChatResponse(reply=msg.get("content", ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """Stream the assistant reply as chunked text (use fetch+ReadableStream in frontend to consume)."""
    messages = []
    if req.history:
        messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    try:
        def gen():
            try:
                for chunk in harness.chat_stream(messages):
                    # yield raw text chunks; the frontend reads and appends
                    yield chunk
            except Exception as ex:
                # yield an error marker then stop
                yield f"\n[ERROR] {str(ex)}"

        return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan", response_model=List[ShotOut])
def plan_endpoint(req: PlanRequest):
    try:
        shots = harness.plan_shots(req.story_prompt, shot_count=req.shot_count)
        out = [ShotOut(id=s.id, prompt=s.prompt, duration_seconds=s.duration_seconds, camera=s.camera) for s in shots]
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
def health():
    return {"ok": True, "llm_configured": bool(settings.llm_api_token or None)}


@app.get("/api/db/health")
def db_health():
    try:
        return check_mysql_connection(mysql_settings_from_app_settings(settings))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/workbench/state")
def workbench_state(account: Dict[str, Any] = Depends(require_account)):
    state = workbench_store.state()
    state["current_user"] = account
    if auth_store is not None:
        state["wallet"] = auth_store.wallet(account["id"])
    return state


@app.post("/api/assets")
def create_asset(req: AssetRequest, account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.create_asset(model_payload(req))


@app.get("/api/assets")
def list_assets(account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.list_assets()


@app.post("/api/tasks")
def create_task(req: TaskRequest, account: Dict[str, Any] = Depends(require_account)):
    known_assets = {asset["id"] for asset in workbench_store.list_assets()}
    missing_assets = [asset_id for asset_id in req.asset_ids if asset_id not in known_assets]
    if missing_assets:
        raise HTTPException(status_code=404, detail=f"Assets not found: {', '.join(missing_assets)}")
    payload = model_payload(req)
    payload["subtitle_cues"] = [model_payload(cue) for cue in req.subtitle_cues]
    return workbench_store.create_task(payload)


@app.get("/api/tasks")
def list_tasks(account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.list_tasks()


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, account: Dict[str, Any] = Depends(require_account)):
    task = workbench_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/tasks/{task_id}/run")
def run_task(task_id: str, account: Dict[str, Any] = Depends(require_account)):
    task = workbench_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled task cannot be run")

    output_dir = Path(settings.output_dir).expanduser() / "workbench" / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    srt_path = output_dir / "subtitles.srt"
    if task.get("subtitle_cues"):
        srt_path.write_text(build_srt(task["subtitle_cues"]), encoding="utf-8")

    manifest = {
        "task_id": task_id,
        "title": task["title"],
        "module": task["module"],
        "asset_ids": task.get("asset_ids", []),
        "edit_profile": task.get("edit_profile", {}),
        "subtitle_path": str(srt_path) if task.get("subtitle_cues") else "",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return workbench_store.update_task(
        task_id,
        {
            "status": "completed",
            "progress": 100,
            "outputs": {"manifest": str(manifest_path), "subtitle": manifest["subtitle_path"]},
            "error": "",
        },
    )


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, account: Dict[str, Any] = Depends(require_account)):
    if not workbench_store.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return workbench_store.update_task(task_id, {"status": "cancelled", "progress": 0})


@app.get("/api/tasks/{task_id}/download")
def download_task_output(task_id: str, kind: str = "manifest", account: Dict[str, Any] = Depends(require_account)):
    task = workbench_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    path_value = task.get("outputs", {}).get(kind)
    if not path_value:
        raise HTTPException(status_code=404, detail="Output not found")
    path = Path(path_value)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file missing")
    return FileResponse(str(path))


@app.post("/api/subtitles/srt")
def export_srt(req: SrtRequest, account: Dict[str, Any] = Depends(require_account)):
    return {"srt": build_srt([model_payload(cue) for cue in req.cues])}


@app.post("/api/voiceovers")
def create_voiceover(req: VoiceoverRequest, account: Dict[str, Any] = Depends(require_account)):
    output_dir = Path(settings.output_dir).expanduser() / "workbench" / "voiceovers"
    provider = MockVoiceoverProvider()
    payload = model_payload(req)
    audio_path = provider.synthesize(req.text, payload, output_dir)
    payload["audio_path"] = audio_path
    return payload


@app.get("/api/membership")
def membership(account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.membership()


@app.post("/api/orders")
def create_order(req: OrderRequest, account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.create_order(model_payload(req))


@app.get("/api/admin/summary")
def admin_summary(account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.admin_summary()


@app.put("/api/admin/provider-config")
def update_provider_config(req: ProviderConfigRequest, account: Dict[str, Any] = Depends(require_account)):
    return workbench_store.upsert_provider_config(model_payload(req))


@app.get("/api/wallet")
def wallet(account: Dict[str, Any] = Depends(require_account)):
    if auth_store is None:
        raise HTTPException(status_code=503, detail="Authentication store is not configured")
    return auth_store.wallet(account["id"])


@app.post("/api/wallet/recharge")
def recharge_wallet(req: WalletChangeRequest, account: Dict[str, Any] = Depends(require_account)):
    if auth_store is None:
        raise HTTPException(status_code=503, detail="Authentication store is not configured")
    try:
        return auth_store.recharge(account["id"], req.amount, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/wallet/consume")
def consume_wallet(req: WalletChangeRequest, account: Dict[str, Any] = Depends(require_account)):
    if auth_store is None:
        raise HTTPException(status_code=503, detail="Authentication store is not configured")
    try:
        return auth_store.consume(account["id"], req.amount, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
