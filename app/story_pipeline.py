from typing import List

from .config import Settings
from .image_generator import get_image_client
from .models import SceneSpec, ShotSpec
from .planner import ShotPlanner
from .script_writer import ScriptWriter


class SceneStoryboardPipeline:
    def __init__(self, settings: Settings, image_provider: str = "mock"):
        self.settings = settings
        self.script_writer = ScriptWriter(settings)
        self.image_client = get_image_client(settings, image_provider)

    def generate_scene_storyboard(self, plot: str, shot_count: int = None) -> List[SceneSpec]:
        scenes = self.script_writer.generate(plot, shot_count=shot_count)
        for scene in scenes:
            scene.image_path = self.image_client.generate(scene.image_prompt, scene.id)
        return scenes

    def build_shot_plan(self, scenes: List[SceneSpec]) -> List[ShotSpec]:
        planner = ShotPlanner(self.settings)
        shot_plan = []
        for scene in scenes:
            prompt = (
                f"{scene.description}, {scene.camera}, storyboard image reference: {scene.image_path}, "
                "cinematic composition, natural motion, dramatic lighting, detailed environment, ultra-detailed"
            )
            shot_plan.append(
                ShotSpec(
                    id=scene.id,
                    prompt=prompt,
                    duration_seconds=scene.duration_seconds,
                    camera=scene.camera,
                )
            )
        return shot_plan
