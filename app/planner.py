import re
from typing import List, Optional

from .config import Settings
from .models import ShotSpec


class ShotPlanner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build_plan(
        self,
        story_prompt: str,
        shot_count: Optional[int] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
    ) -> List[ShotSpec]:
        shot_count = shot_count or self.settings.default_shots
        min_duration = min_duration or self.settings.min_duration
        max_duration = max_duration or self.settings.max_duration

        shot_prompts = self._split_story_into_shots(story_prompt, shot_count)
        durations = self._build_durations(shot_count, min_duration, max_duration)

        return [
            ShotSpec(
                id=f"shot_{idx:02d}",
                prompt=self._shape_prompt(prompt, idx),
                duration_seconds=durations[idx],
                camera=self._camera_for_index(idx),
            )
            for idx, prompt in enumerate(shot_prompts)
        ]

    def _split_story_into_shots(self, story_prompt: str, shot_count: int) -> List[str]:
        candidates = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+|\n+", story_prompt) if segment.strip()]
        if not candidates:
            candidates = [story_prompt.strip()]

        if len(candidates) >= shot_count:
            selected = candidates[:shot_count]
        else:
            selected = candidates.copy()
            while len(selected) < shot_count:
                selected.append(candidates[-1])

        return selected

    def _build_durations(self, shot_count: int, min_duration: int, max_duration: int) -> List[int]:
        if shot_count <= 1:
            return [max(min_duration, min(max_duration, (min_duration + max_duration) // 2))]

        step = (max_duration - min_duration) / (shot_count - 1)
        durations = []
        for idx in range(shot_count):
            duration = round(min_duration + (step * idx))
            durations.append(max(min_duration, min(max_duration, duration)))
        return durations

    def _shape_prompt(self, prompt: str, index: int) -> str:
        camera_motion = self._camera_for_index(index)
        return (
            f"{prompt}, {camera_motion}, cinematic composition, natural motion, detailed environment, "
            "dramatic lighting, high quality, realistic texture, smooth camera movement, ultra-detailed"
        )

    def _camera_for_index(self, index: int) -> str:
        camera_styles = [
            "wide establishing aerial shot",
            "tracking side dolly shot",
            "low-angle hero close-up",
            "over-the-shoulder dynamic shot",
            "top-down reveal shot",
        ]
        return camera_styles[index % len(camera_styles)]
