from pathlib import Path
from functools import lru_cache
import csv
import os


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

NOTICE_PATHS = (Path(DATA_DIR) / 'HSK_NOTICE.txt',)


@lru_cache(maxsize=1)
def load_levels() -> dict:
    """Load the local HSK 3.0 character recognition levels."""
    file_path = os.path.join(DATA_DIR, "HSK-3.0-characters.csv")
    hsk_map = {}
    with open(file_path, newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            character = (row.get("Character") or "").strip()
            level = (row.get("Level") or "").strip()
            if len(character) == 1 and level in {
                "1", "2", "3", "4", "5", "6", "7-9"
            }:
                hsk_map[character] = level

    return hsk_map


def level(character: str) -> str:
    return load_levels().get(character, "")
