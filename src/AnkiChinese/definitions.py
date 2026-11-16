"""Load editable compact glosses with their original dictionary references."""
import json
import re
from pathlib import Path

from .config import is_hanzi


DEFAULT_GLOSSES_PATH = Path(__file__).resolve().parent / "data" / "compact_glosses.json"


def load_compact_glosses(path=DEFAULT_GLOSSES_PATH):
    """Read once per generation so edits take effect in the next CLI or GUI run."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Compact glosses must map characters to pronunciation entries")
    for character, readings in data.items():
        if not is_hanzi(character) or not isinstance(readings, dict):
            raise ValueError("Invalid character entry in compact glosses: " + character)
        for reading, entry in readings.items():
            if not re.fullmatch(r"[a-züv:]+[1-5]", reading) or not isinstance(entry, dict):
                raise ValueError("Invalid compact gloss reading for " + character)
            glosses = entry.get("glosses")
            if not isinstance(glosses, list) or not glosses or any(
                not isinstance(gloss, str) or not gloss.strip() or any(is_hanzi(char) for char in gloss)
                for gloss in glosses
            ):
                raise ValueError("Compact glosses must contain nonempty English glosses for " + character + " " + reading)
            source = entry.get("source_definitions", [])
            if not isinstance(source, list) or any(not isinstance(definition, str) for definition in source):
                raise ValueError("Invalid source definitions for " + character + " " + reading)
    return data
