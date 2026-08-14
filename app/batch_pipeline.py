import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .assembler import VideoAssembler
from .config import Settings
from .generator import MockVideoClient, ReplicateClient
from .story_pipeline import SceneStoryboardPipeline


class BatchVideoGenerator:
    def __init__(self, settings: Settings, provider: str = None, image_provider: str = None):
        self.settings = settings
        self.provider = (provider or settings.provider).lower()
        self.image_provider = (image_provider or settings.image_provider or "mock").lower()

    def load_stories(self, input_path: Union[str, Path]) -> List[str]:
        path = Path(input_path).expanduser()
        text = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()

        if suffix == ".json":
            data = json.loads(text)
            if isinstance(data, list):
                return [self._coerce_story(item) for item in data]
            if isinstance(data, dict):
                for key in ("stories", "prompts", "items"):
                    if key in data:
                        values = data[key]
                        if isinstance(values, list):
                            return [self._coerce_story(item) for item in values]
            raise ValueError("JSON batch file must contain a list of stories under 'stories' or at the root.")

        stories = []
        for line in text.splitlines():
            item = line.strip()
            if not item or item.startswith("#"):
                continue
            stories.append(item)
        return stories

    def generate_batch(self, stories: List[str], batch_name: str = "batch", workers: Optional[int] = None) -> List[Dict[str, Any]]:
        results = []
        batch_root = Path(self.settings.output_dir).expanduser() / batch_name
        batch_root.mkdir(parents=True, exist_ok=True)

        if not stories:
            return results

        max_workers = workers or min(32, max(1, (os.cpu_count() or 1) + 4))
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for idx, story in enumerate(stories, start=1):
                futures.append(executor.submit(self._process_single_story, story, idx, batch_root, len(stories)))

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(f"Completed story {result['story_index']}/{len(stories)} -> {result['video_path']}")

        results.sort(key=lambda item: item["story_index"])
        manifest_path = batch_root / "manifest.json"
        manifest_path.write_text(json.dumps({"batch_name": batch_name, "stories": results}, ensure_ascii=False, indent=2), encoding="utf-8")
        return results

    def _process_single_story(self, story: str, index: int, batch_root: Path, total: int) -> Dict[str, Any]:
        slug = self._slugify_name(story)
        story_dir = batch_root / f"story_{index:04d}_{slug}"
        story_dir.mkdir(parents=True, exist_ok=True)

        story_settings = replace(self.settings, output_dir=story_dir)
        pipeline = SceneStoryboardPipeline(story_settings, image_provider=self.image_provider)
        scenes = pipeline.generate_scene_storyboard(story, shot_count=self.settings.default_shots)
        shot_plan = pipeline.build_shot_plan(scenes)
        client = self._get_client(story_settings, self.provider)
        generated_paths = []
        for shot in shot_plan:
            generated_paths.append(client.generate(shot))

        assembler = VideoAssembler(story_settings)
        final_video = assembler.concat(generated_paths, output_name="final_story.mp4")
        return {
            "story_index": index,
            "story": story,
            "video_path": final_video,
            "scene_count": len(scenes),
            "image_paths": [scene.image_path for scene in scenes],
        }

    def _get_client(self, settings: Settings, provider_name: str):
        provider = provider_name.lower()
        if provider == "mock":
            return MockVideoClient(settings)
        if provider == "replicate":
            return ReplicateClient(settings)
        raise ValueError(f"Unsupported provider: {provider}")

    def _coerce_story(self, item: Any) -> str:
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            for key in ("story", "prompt", "text", "title"):
                value = item.get(key)
                if isinstance(value, str):
                    return value.strip()
        raise ValueError(f"Unsupported story item: {item!r}")

    def _slugify_name(self, story: str) -> str:
        cleaned = story.strip().lower()
        cleaned = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '-' for ch in cleaned)
        cleaned = cleaned.strip('-')
        return cleaned[:40] or "story"
