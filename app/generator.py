import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import Settings
from .models import ShotSpec


class VideoGenerationClient:
    def generate(self, shot: ShotSpec) -> str:
        raise NotImplementedError


class MockVideoClient(VideoGenerationClient):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, shot: ShotSpec) -> str:
        output_dir = Path(self.settings.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{shot.id}.mp4"

        ffmpeg_bin = self.settings.ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        command = [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a1a:s=1280x720:d={max(1, min(30, shot.duration_seconds))}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            output_path.write_bytes(b"mock video")
        return str(output_path)


class ReplicateClient(VideoGenerationClient):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.settings.api_token}",
            "Content-Type": "application/json",
        })

    def generate(self, shot: ShotSpec) -> str:
        if not self.settings.api_base_url or not self.settings.model_name or not self.settings.api_token:
            raise ValueError(
                "Need VIDEO_API_BASE_URL, VIDEO_API_TOKEN, and VIDEO_MODEL_NAME in the environment before generating videos."
            )

        payload = {
            "input": {
                "prompt": shot.prompt,
                "negative_prompt": shot.negative_prompt,
                "duration": shot.duration_seconds,
                "fps": self.settings.fps,
                "aspect_ratio": self.settings.aspect_ratio,
                "guidance_scale": shot.guidance_scale,
            }
        }

        create_url = f"{self.settings.api_base_url.rstrip('/')}/v1/models/{self.settings.model_name}/predictions"
        response = self.session.post(create_url, json=payload, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        data = response.json()

        prediction_id = data.get("id") or data.get("prediction_id")
        if not prediction_id:
            raise RuntimeError(f"Unexpected response from model API: {data}")

        status_url = f"{self.settings.api_base_url.rstrip('/')}/v1/predictions/{prediction_id}"
        while True:
            status_response = self.session.get(status_url, timeout=self.settings.timeout_seconds)
            status_response.raise_for_status()
            status_data = status_response.json()
            state = str(status_data.get("status", "")).lower()

            if state in {"succeeded", "completed"}:
                output_value = status_data.get("output")
                video_url = self._extract_video_url(output_value)
                if not video_url:
                    raise RuntimeError(f"Video URL missing from API output: {status_data}")
                break

            if state in {"failed", "canceled", "cancelled", "error"}:
                raise RuntimeError(f"Video generation failed: {status_data}")

            time.sleep(5)

        destination = Path(self.settings.output_dir).expanduser() / f"{shot.id}.mp4"
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._download_file(video_url, destination)
        return str(destination)

    def _extract_video_url(self, output_value: Any) -> Optional[str]:
        if isinstance(output_value, str):
            return output_value if output_value.lower().endswith((".mp4", ".mov", ".webm")) else None
        if isinstance(output_value, list):
            for item in output_value:
                url = self._extract_video_url(item)
                if url:
                    return url
            return None
        if isinstance(output_value, dict):
            for key in ("url", "video_url", "output", "result"):
                value = output_value.get(key)
                if value:
                    nested = self._extract_video_url(value)
                    if nested:
                        return nested
            return None
        return None

    def _download_file(self, url: str, destination: Path) -> None:
        response = self.session.get(url, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        destination.write_bytes(response.content)
