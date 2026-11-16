"""Interchangeable adapters and the default source configuration."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sources:
    """Adapters return normalized data using these methods:

    dictionary.lookup(character, word_scores) -> CharacterEntries
    frequency.load_word_scores() -> {word: occurrences_per_million_words}
    frequency.load_dialogue_word_scores() -> {word: dialogue_occurrences_per_million_words}
        (optional, used to qualify names)
    frequency.load_internet_word_scores() -> {word: internet_occurrences_per_million_words}
        (optional, used to qualify names)
    frequency.character_frequency(character) -> (rank, occurrences_per_million)
    formation.formation(character) -> text
    levels.level(character) -> HSK level text
    audio.get_recordings(readings, max_concurrent, max_per_second)
        -> iterable of (original_reading, local_path_or_none, error_text)

    Formation, levels and audio are optional. Each adapter may provide
    NOTICE_PATHS containing its attribution and license files.
    """
    dictionary: object
    frequency: object
    formation: object = None
    levels: object = None
    audio: object = None

    @property
    def notice_paths(self):
        adapters = (self.dictionary, self.frequency, self.formation, self.levels, self.audio)
        notices = {}
        for adapter in adapters:
            for path in getattr(adapter, "NOTICE_PATHS", ()):
                path = Path(path)
                if path.name in notices and notices[path.name] != path:
                    raise ValueError("Source notices must have unique filenames: " + path.name)
                notices[path.name] = path
        return tuple(notices.values())


def default_sources(audio_cache_dir):
    """Keep the choice of bundled providers in one place."""
    from . import cc_cedict, frequency, hsk, make_me_a_hanzi
    from .audio_cmn import AudioStore

    return Sources(cc_cedict, frequency, make_me_a_hanzi, hsk, AudioStore(audio_cache_dir))
