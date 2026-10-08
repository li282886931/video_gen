from pathlib import Path
from typing import Any, Dict, Iterable, List


def format_srt_time(milliseconds: int) -> str:
    milliseconds = max(0, int(milliseconds))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    seconds = milliseconds // 1_000
    millis = milliseconds % 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_srt(cues: Iterable[Dict[str, Any]]) -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        start = format_srt_time(cue.get("start_ms", 0))
        end = format_srt_time(cue.get("end_ms", 0))
        text = str(cue.get("text", "")).strip()
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


class VideoOperationPlanner:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def build_processing_command(self, input_path: str, output_path: Path, operations: Dict[str, Any]) -> List[str]:
        command = [self.ffmpeg_bin, "-y", "-i", str(input_path)]
        filters = self._video_filters(operations)
        if filters:
            command.extend(["-vf", ",".join(filters)])
        if operations.get("mute"):
            command.append("-an")
        export = operations.get("export", {})
        resolution = export.get("resolution")
        if resolution and not operations.get("crop"):
            command.extend(["-s", str(resolution)])
        fps = export.get("fps")
        if fps:
            command.extend(["-r", str(fps)])
        bitrate = export.get("bitrate")
        if bitrate:
            command.extend(["-b:v", str(bitrate)])
        command.append(str(output_path))
        return command

    def build_extract_frame_command(self, input_path: str, output_pattern: Path, fps: int = 1) -> List[str]:
        return [self.ffmpeg_bin, "-y", "-i", str(input_path), "-vf", f"fps={fps}", str(output_pattern)]

    def build_concat_command(self, file_list_path: Path, output_path: Path) -> List[str]:
        return [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(file_list_path),
            "-c",
            "copy",
            str(output_path),
        ]

    def _video_filters(self, operations: Dict[str, Any]) -> List[str]:
        filters: List[str] = []
        crop = operations.get("crop")
        if crop:
            filters.append(f"crop={crop['width']}:{crop['height']}:{crop.get('x', 0)}:{crop.get('y', 0)}")
        speed = operations.get("speed")
        if speed and float(speed) > 0 and float(speed) != 1:
            filters.append(f"setpts={round(1 / float(speed), 4)}*PTS")
        if operations.get("mirror"):
            filters.append("hflip")
        watermark = operations.get("watermark")
        if watermark and watermark.get("mode") == "blur":
            x = watermark.get("x", 0)
            y = watermark.get("y", 0)
            width = watermark.get("width", 100)
            height = watermark.get("height", 100)
            filters.append(
                "split[base][mark];"
                f"[mark]crop={width}:{height}:{x}:{y},boxblur=12[blur];"
                f"[base][blur]overlay={x}:{y}"
            )
        return filters
