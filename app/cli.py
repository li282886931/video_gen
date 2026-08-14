import argparse
from pathlib import Path
from typing import Optional

from .assembler import VideoAssembler
from .batch_pipeline import BatchVideoGenerator
from .config import get_settings
from .generator import MockVideoClient, ReplicateClient
from .planner import ShotPlanner
from .story_pipeline import SceneStoryboardPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate multiple video shots from a prompt and stitch them with FFmpeg.")
    parser.add_argument("--story", help="Story prompt or theme for the final short video.")
    parser.add_argument("--stories-file", help="Text file with one story per line, or JSON file containing a list of stories.")
    parser.add_argument("--batch-name", default="batch", help="Name of the subfolder used to store all videos in batch mode.")
    parser.add_argument("--batch-limit", type=int, default=None, help="Limit the number of stories processed in batch mode.")
    parser.add_argument("--workers", type=int, default=None, help="Parallel worker count in batch mode. Defaults to CPU-based automatic tuning.")
    parser.add_argument("--shots", type=int, default=None, help="Number of shots to create. Defaults to env or 4.")
    parser.add_argument("--min-duration", type=int, default=None, help="Minimum duration of each shot in seconds.")
    parser.add_argument("--max-duration", type=int, default=None, help="Maximum duration of each shot in seconds.")
    parser.add_argument("--provider", choices=["replicate", "mock"], default=None, help="Generation provider to use.")
    parser.add_argument("--image-provider", choices=["mock", "openai", "openai-compatible", "image-api"], default=None, help="Image generation provider to use for storyboard visuals.")
    parser.add_argument("--output-name", default="final_story.mp4", help="Name of the assembled output video.")
    parser.add_argument("--no-script", action="store_true", help="Skip automatic script reasoning and generate shots directly from the storyline.")
    return parser


def get_client(settings, provider_name: Optional[str]):
    provider = (provider_name or settings.provider).lower()
    if provider == "mock":
        return MockVideoClient(settings)
    if provider == "replicate":
        return ReplicateClient(settings)
    raise ValueError(f"Unsupported provider: {provider}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.story and not args.stories_file:
        parser.error("Either --story or --stories-file is required.")

    settings = get_settings()

    if args.stories_file:
        generator = BatchVideoGenerator(settings, provider=args.provider, image_provider=args.image_provider)
        stories = generator.load_stories(args.stories_file)
        if args.batch_limit is not None:
            stories = stories[:args.batch_limit]
        results = generator.generate_batch(stories, batch_name=args.batch_name, workers=args.workers)
        print(f"Batch generation complete: {len(results)} videos generated under {Path(settings.output_dir).expanduser() / args.batch_name}")
        return

    planner = ShotPlanner(settings)
    if args.no_script:
        shot_plan = planner.build_plan(
            story_prompt=args.story,
            shot_count=args.shots,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
        )
    else:
        pipeline = SceneStoryboardPipeline(settings, image_provider=args.image_provider or settings.image_provider)
        scenes = pipeline.generate_scene_storyboard(args.story, shot_count=args.shots)
        print("Storyboard generated:")
        for scene in scenes:
            print(f"- {scene.id}: {scene.title} | {scene.duration_seconds}s | image={scene.image_path}")
        shot_plan = pipeline.build_shot_plan(scenes)

    client = get_client(settings, args.provider)
    generated_paths = []
    for idx, shot in enumerate(shot_plan, start=1):
        print(f"[{idx}/{len(shot_plan)}] Generating shot '{shot.id}' ({shot.duration_seconds}s): {shot.prompt}")
        shot_path = client.generate(shot)
        generated_paths.append(shot_path)
        print(f"Saved: {shot_path}")

    assembler = VideoAssembler(settings)
    final_path = assembler.concat(generated_paths, output_name=args.output_name)
    print(f"Final assembled video: {final_path}")


if __name__ == "__main__":
    main()
