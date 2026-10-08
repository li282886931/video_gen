from pathlib import Path
from typing import Dict, Protocol


class VoiceoverProvider(Protocol):
    def synthesize(self, text: str, config: Dict[str, object], output_dir: Path) -> str:
        ...


class MockVoiceoverProvider:
    def synthesize(self, text: str, config: Dict[str, object], output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / "voiceover.txt"
        audio_path.write_text(
            f"voice={config.get('voice', 'standard')}\nspeed={config.get('speed', 1)}\n{text}\n",
            encoding="utf-8",
        )
        return str(audio_path)
