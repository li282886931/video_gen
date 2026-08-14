from dataclasses import dataclass


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
