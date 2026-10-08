from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ShotSpec:
    id: str
    prompt: str
    duration_seconds: int
    negative_prompt: str = "blurry, distorted, low quality, flicker, bad anatomy"
    guidance_scale: float = 7.5
    camera: str = "cinematic camera move"

    def to_api_payload(self) -> dict:
        return {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "duration": self.duration_seconds,
            "guidance_scale": self.guidance_scale,
            "camera": self.camera,
        }


@dataclass
class SceneSpec:
    id: str
    title: str
    description: str
    image_prompt: str
    duration_seconds: int
    camera: str = "cinematic camera move"
    image_path: str = ""


@dataclass
class Asset:
    id: str
    name: str
    type: str
    source: str = "local"
    path: str = ""
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchTask:
    id: str
    title: str
    module: str
    status: str = "pending"
    story_prompt: str = ""
    asset_ids: List[str] = field(default_factory=list)
    edit_profile: Dict[str, Any] = field(default_factory=dict)
    subtitle_cues: List[Dict[str, Any]] = field(default_factory=list)
    voiceover: Dict[str, Any] = field(default_factory=dict)
    progress: int = 0
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: str = ""
    updated_at: str = ""
