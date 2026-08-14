from pathlib import Path
from typing import Optional

import requests

from .config import Settings


class ImageGenerationClient:
    def generate(self, prompt: str, scene_id: str) -> str:
        raise NotImplementedError


class MockImageClient(ImageGenerationClient):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, prompt: str, scene_id: str) -> str:
        output_dir = Path(self.settings.output_dir).expanduser() / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{scene_id}.png"
        output_path.write_bytes(b"mock image")
        return str(output_path)


class OpenAIImageClient(ImageGenerationClient):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.settings.image_api_token}",
            "Content-Type": "application/json",
        })

    def generate(self, prompt: str, scene_id: str) -> str:
        if not self.settings.image_api_base_url or not self.settings.image_api_token:
            raise ValueError("Need IMAGE_API_BASE_URL and IMAGE_API_TOKEN to generate scene images.")

        payload = {
            "model": self.settings.image_model_name,
            "prompt": prompt,
            "size": "1024x1024",
        }
        endpoint = f"{self.settings.image_api_base_url.rstrip('/')}/images/generations"
        response = self.session.post(endpoint, json=payload, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        data = response.json()

        image_url = None
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                first = data["data"][0]
                image_url = first.get("url") or first.get("b64_json")
        if not image_url:
            raise RuntimeError(f"Unexpected image API response: {data}")

        output_dir = Path(self.settings.output_dir).expanduser() / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{scene_id}.png"

        if isinstance(image_url, str) and image_url.startswith("data:"):
            image_bytes = image_url.split(",", 1)[1].encode("utf-8")
            output_path.write_bytes(__import__("base64").b64decode(image_bytes))
            return str(output_path)

        image_response = self.session.get(image_url, timeout=self.settings.timeout_seconds)
        image_response.raise_for_status()
        output_path.write_bytes(image_response.content)
        return str(output_path)


def get_image_client(settings: Settings, provider_name: Optional[str] = None) -> ImageGenerationClient:
    provider = (provider_name or settings.image_provider or "mock").lower()
    if provider == "mock":
        return MockImageClient(settings)
    if provider in {"openai", "openai-compatible", "image-api"}:
        return OpenAIImageClient(settings)
    raise ValueError(f"Unsupported image provider: {provider}")
