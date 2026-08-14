import json
import re
from typing import List, Optional

import requests

from .config import Settings
from .models import SceneSpec


class ScriptWriter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, plot: str, shot_count: Optional[int] = None) -> List[SceneSpec]:
        shot_count = shot_count or self.settings.default_shots
        if self._has_llm_config():
            try:
                return self._generate_with_llm(plot, shot_count)
            except Exception:
                pass
        return self._generate_fallback(plot, shot_count)

    def _has_llm_config(self) -> bool:
        return bool(self.settings.llm_api_base_url and self.settings.llm_model_name and self.settings.llm_api_token)

    def _generate_with_llm(self, plot: str, shot_count: int) -> List[SceneSpec]:
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.settings.llm_api_token}",
            "Content-Type": "application/json",
        })
        endpoint = f"{self.settings.llm_api_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.llm_model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional short-video story director. Return valid JSON only with an array of scenes. Each scene must include: id, title, description, image_prompt, duration_seconds, camera. Keep each scene between 15 and 30 seconds.",
                },
                {
                    "role": "user",
                    "content": f"Create a {shot_count}-scene storyboard for this topic: {plot}. Return only JSON array, no markdown fences."
                },
            ],
            "temperature": 0.7,
        }
        response = session.post(endpoint, json=payload, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed = json.loads(cleaned)
        scenes = []
        for idx, item in enumerate(parsed[:shot_count], start=1):
            duration = int(item.get("duration_seconds", 20))
            scenes.append(SceneSpec(
                id=f"scene_{idx:02d}",
                title=str(item.get("title", f"Scene {idx}")),
                description=str(item.get("description", item.get("prompt", plot))),
                image_prompt=str(item.get("image_prompt", item.get("prompt", plot))),
                duration_seconds=max(self.settings.min_duration, min(self.settings.max_duration, duration)),
                camera=str(item.get("camera", "cinematic camera move")),
            ))
        if not scenes:
            raise ValueError("LLM returned no valid scenes.")
        return scenes

    def _generate_fallback(self, plot: str, shot_count: int) -> List[SceneSpec]:
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+|\n+", plot) if segment.strip()]
        if not sentences:
            sentences = [plot.strip()]

        if len(sentences) >= shot_count:
            selected = sentences[:shot_count]
        else:
            selected = sentences.copy()
            while len(selected) < shot_count:
                selected.append(selected[-1])

        camera_styles = [
            "wide establishing aerial shot",
            "tracking side dolly shot",
            "low-angle hero close-up",
            "over-the-shoulder dynamic shot",
            "top-down reveal shot",
        ]
        scenes = []
        for idx, sentence in enumerate(selected, start=1):
            scenes.append(SceneSpec(
                id=f"scene_{idx:02d}",
                title=f"Scene {idx}",
                description=sentence,
                image_prompt=f"{sentence}, cinematic composition, detailed environment, dramatic lighting, high quality, photorealistic",
                duration_seconds=max(self.settings.min_duration, min(self.settings.max_duration, 15 + (idx % 3) * 5)),
                camera=camera_styles[(idx - 1) % len(camera_styles)],
            ))
        return scenes
