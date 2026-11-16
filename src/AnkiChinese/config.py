"""Shared defaults, paths, and validated input for every frontend."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


def default_audio_cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    return Path(base or Path.home() / ".cache") / "AnkiChinese" / "audio"


def is_hanzi(character):
    return len(character) == 1 and any(low <= ord(character) <= high for low, high in (
        (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x323AF),
    ))


def normalize_characters(values):
    """Deduplicate Hanzi while preserving the caller's order."""
    return tuple(dict.fromkeys(char for value in values for char in value if is_hanzi(char)))


@dataclass(frozen=True)
class GenerationOptions:
    definition_limit: int = 3
    example_limit: int = 5
    audio_concurrency: int = 10
    audio_per_second: int = 5
    audio_cache_dir: Path = field(default_factory=default_audio_cache_dir)

    def __post_init__(self):
        for name in ("definition_limit", "example_limit", "audio_concurrency", "audio_per_second"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("{} must be a positive integer".format(name))
        object.__setattr__(self, "audio_cache_dir", Path(self.audio_cache_dir))


@dataclass(frozen=True)
class RunRequest:
    characters: Iterable[str]
    mode: str
    options: GenerationOptions = field(default_factory=GenerationOptions)
    output_path: Path = Path("ankichinese_output")
    deck_name: str = ""
    model_name: str = ""
    include_existing: bool = False

    def __post_init__(self):
        if self.mode not in ("anki", "csv", "update"):
            raise ValueError("Unknown output mode: " + self.mode)
        if self.mode == "update" and not (self.deck_name and self.model_name):
            raise ValueError("Select an Anki deck and note type")
        object.__setattr__(self, "characters", normalize_characters(self.characters))
        output_path = Path(self.output_path)
        if self.mode != "update":
            if not output_path.name or output_path.is_dir():
                raise ValueError("Choose an output file")
            suffix = ".csv" if self.mode == "csv" else ".apkg"
            if output_path.suffix.lower() != suffix:
                output_path = Path(str(output_path) + suffix)
        object.__setattr__(self, "output_path", output_path)
        if not self.characters and not (self.mode == "update" and self.include_existing):
            raise ValueError("No Hanzi found")
