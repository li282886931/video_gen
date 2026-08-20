from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import get_settings
from .harness import Harness
from .models import ShotSpec


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
BASE_DIR = Path(__file__).parent


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


# Simple static UI endpoints (for local quick demo)
@app.get("/", response_class=HTMLResponse)
def index():
    path = BASE_DIR / "chat_ui.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="UI file not found")
    return FileResponse(str(path))


@app.get("/static_chat_ui.js")
def chat_js():
    path = BASE_DIR / "static_chat_ui.js"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(path))


@app.get("/static_chat_ui.css")
def chat_css():
    path = BASE_DIR / "static_chat_ui.css"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(str(path))
