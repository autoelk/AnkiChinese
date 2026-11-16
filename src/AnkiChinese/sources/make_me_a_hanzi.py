from pathlib import Path
from functools import lru_cache
import json
import os


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

NOTICE_PATHS = (Path(DATA_DIR) / 'MAKE_ME_A_HANZI_NOTICE.txt', Path(DATA_DIR) / 'MAKE_ME_A_HANZI_LGPL.txt',)


@lru_cache(maxsize=1)
def _load_etymologies() -> dict:
    """Load Make Me a Hanzi's JSON-lines dictionary etymology data."""
    file_path = os.path.join(DATA_DIR, "make-me-a-hanzi-dictionary.txt")
    formation_map = {}
    with open(file_path, encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            character = row.get("character", "")
            etymology = row.get("etymology")
            if len(character) == 1 and isinstance(etymology, dict):
                formation_map[character] = etymology

    return formation_map


def formation(character: str) -> str:
    etymology = _load_etymologies().get(character)
    if not etymology:
        return ""

    kind = (etymology.get("type") or "").replace("-", " ").capitalize()
    hint = (etymology.get("hint") or "").strip()
    phonetic = etymology.get("phonetic")
    semantic = etymology.get("semantic")
    if kind == "Pictophonetic":
        parts = []
        if semantic:
            parts.append(f"{semantic} suggests meaning")
        if phonetic:
            parts.append(f"{phonetic} suggests sound")
        explanation = "; ".join(parts)
        if hint:
            explanation = f"{explanation} ({hint})" if explanation else hint
        return f"{kind}: {explanation}" if explanation else kind
    return f"{kind}: {hint}" if hint else kind
