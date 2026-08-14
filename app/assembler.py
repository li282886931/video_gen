import subprocess
from pathlib import Path

from .config import Settings


class VideoAssembler:
    def __init__(self, settings: Settings):
        self.settings = settings

    def concat(self, shot_paths: list[str], output_name: str = "final_story.mp4") -> str:
        if not shot_paths:
            raise ValueError("At least one shot is required to assemble the final video.")

        output_dir = Path(self.settings.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        concat_file = output_dir / "concat.txt"
        with concat_file.open("w", encoding="utf-8") as handle:
            for shot_path in shot_paths:
                safe_path = Path(shot_path).expanduser().resolve().as_posix().replace("\\", "/")
                handle.write(f"file '{safe_path}'\n")

        final_path = output_dir / output_name
        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(final_path),
        ]

        result = subprocess.run(command, capture_output=True)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            raise RuntimeError(f"FFmpeg concat failed: {stderr or stdout}")

        return str(final_path)
