"""Shared dictionary entries, cards, and progress messages."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

@dataclass(frozen=True)
class Meaning:
    """An English definition safe for card prompts, with normalized ranking flags."""
    definition: str
    is_name: bool = False
    is_rare: bool = False
    is_formal: bool = False

@dataclass(frozen=True)
class DictionaryEntry:
    """Pronunciation uses lowercase, tone-number pinyin syllables, one per Hanzi."""
    pronunciation: Tuple[str, ...]
    meanings: Tuple[Meaning, ...]
    source_definitions: Tuple[str, ...] = ()

@dataclass(frozen=True)
class CharacterEntries:
    """Normalized entries with blended and source-specific word frequencies per million."""
    character: str
    entries: Tuple[DictionaryEntry, ...]
    words: Tuple[Tuple[str, Tuple[DictionaryEntry, ...], float], ...]
    traditional: str
    fallback_definition: str
    dialogue_frequencies: dict = field(default_factory=dict)
    missing_word_frequencies: frozenset = frozenset()
    internet_frequencies: dict = field(default_factory=dict)
    preferred_reading: str = ""
    usage_examples: Tuple["ExampleWord", ...] = ()

@dataclass(frozen=True)
class ExampleWord:
    word: str
    pronunciation: Tuple[str, ...]
    definitions: Tuple[str, ...]

@dataclass(frozen=True)
class Card:
    character: str
    traditional: str
    readings: Tuple[str, ...]
    definitions: Tuple[str, ...]
    examples: Tuple[ExampleWord, ...]
    formation: str = ""
    hsk_level: str = ""
    frequency_rank: Optional[int] = None
    frequency_per_million: Optional[float] = None
    audio_path: Optional[Path] = None
    selection_notes: Tuple[str, ...] = ()
    selection_warnings: Tuple[str, ...] = ()
    selection_info: Tuple[str, ...] = ()

@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    completed: int = 0
    total: int = 0
    message: str = ""


def ignore_progress(event):
    pass
