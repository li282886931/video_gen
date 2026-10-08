import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def resolve_ffmpeg_bin() -> str:
    env_value = os.getenv("FFMPEG_BIN", "").strip()
    if env_value:
        return env_value
    path_value = shutil.which("ffmpeg")
    if path_value:
        return path_value
    candidates = [
        r"C:\Users\A\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return "ffmpeg"


@dataclass
class Settings:
    provider: str = "replicate"
    api_base_url: str = ""
    api_token: str = ""
    model_name: str = ""
    llm_api_base_url: str = ""
    llm_api_token: str = ""
    llm_model_name: str = ""
    image_api_base_url: str = ""
    image_api_token: str = ""
    image_model_name: str = ""
    image_provider: str = "mock"
    output_dir: Path = Path("output")
    fps: int = 24
    aspect_ratio: str = "16:9"
    min_duration: int = 15
    max_duration: int = 30
    default_shots: int = 4
    timeout_seconds: int = 180
    ffmpeg_bin: str = "ffmpeg"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "video_gen_workbench"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            provider=os.getenv("VIDEO_PROVIDER", "replicate").strip() or "replicate",
            api_base_url=os.getenv("VIDEO_API_BASE_URL", "").strip(),
            api_token=os.getenv("VIDEO_API_TOKEN", "").strip(),
            model_name=os.getenv("VIDEO_MODEL_NAME", "").strip(),
            llm_api_base_url=os.getenv("LLM_API_BASE_URL", "").strip(),
            llm_api_token=os.getenv("LLM_API_TOKEN", "").strip(),
            llm_model_name=os.getenv("LLM_MODEL_NAME", "").strip(),
            image_api_base_url=os.getenv("IMAGE_API_BASE_URL", "").strip(),
            image_api_token=os.getenv("IMAGE_API_TOKEN", "").strip(),
            image_model_name=os.getenv("IMAGE_MODEL_NAME", "").strip(),
            image_provider=os.getenv("IMAGE_PROVIDER", "mock").strip() or "mock",
            output_dir=Path(os.getenv("VIDEO_OUTPUT_DIR", "./output").strip()).expanduser(),
            fps=int(os.getenv("VIDEO_FPS", "24")),
            aspect_ratio=os.getenv("VIDEO_ASPECT_RATIO", "16:9").strip() or "16:9",
            min_duration=int(os.getenv("VIDEO_MIN_DURATION", "15")),
            max_duration=int(os.getenv("VIDEO_MAX_DURATION", "30")),
            default_shots=int(os.getenv("VIDEO_DEFAULT_SHOTS", "4")),
            timeout_seconds=int(os.getenv("VIDEO_TIMEOUT_SECONDS", "180")),
            ffmpeg_bin=resolve_ffmpeg_bin(),
            mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1").strip() or "127.0.0.1",
            mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
            mysql_user=os.getenv("MYSQL_USER", "root").strip() or "root",
            mysql_password=os.getenv("MYSQL_PASSWORD", "").strip(),
            mysql_database=os.getenv("MYSQL_DATABASE", "video_gen_workbench").strip() or "video_gen_workbench",
        )


def get_settings() -> Settings:
    return Settings.from_env()
