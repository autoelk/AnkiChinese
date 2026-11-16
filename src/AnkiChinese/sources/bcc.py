"""BCC frequency scores: two parts spoken, one part news."""
import csv
import zipfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

NOTICE_PATHS = (Path(DATA_DIR) / 'BCC_NOTICE.txt',)
CORPUS_WEIGHTS = (("dialogue", 2 / 3), ("news", 1 / 3))
PER_MILLION = 1_000_000


def _load_counts(corpus, kind):
    with zipfile.ZipFile(DATA_DIR / f"BCC-{corpus}-{kind}-frequencies.zip") as archive:
        with archive.open(archive.namelist()[0]) as source:
            rows = [(row["token"].strip(), int(row["count"]))
                    for row in csv.DictReader(line.decode("utf-8") for line in source)]
    return sorted(rows, key=lambda item: (-item[1], item[0]))


@lru_cache(maxsize=1)
def _word_frequencies_by_corpus():
    frequencies = {}
    for corpus, _ in CORPUS_WEIGHTS:
        rows = _load_counts(corpus, "word")
        total = sum(count for _, count in rows)
        frequencies[corpus] = {word: PER_MILLION * count / total for word, count in rows} if total else {}
    return frequencies


@lru_cache(maxsize=1)
def load_word_scores():
    """Blend occurrences per million words, normalizing each corpus separately."""
    scores = defaultdict(float)
    for corpus, weight in CORPUS_WEIGHTS:
        for word, frequency in _word_frequencies_by_corpus()[corpus].items():
            scores[word] += weight * frequency
    return dict(scores)


def load_dialogue_word_scores():
    return _word_frequencies_by_corpus()["dialogue"]


def load_news_word_scores():
    return _word_frequencies_by_corpus()["news"]


@lru_cache(maxsize=1)
def load_character_frequencies():
    """Blend occurrences per million characters, then rank the result."""
    scores = defaultdict(float)
    for corpus, weight in CORPUS_WEIGHTS:
        rows = _load_counts(corpus, "character")
        total = sum(count for _, count in rows)
        for character, count in rows:
            scores[character] += weight * PER_MILLION * count / total
    ordered = sorted(scores, key=lambda character: (-scores[character], character))
    return {character: (rank, round(scores[character], 2))
            for rank, character in enumerate(ordered, 1)}


def character_frequency(character):
    return load_character_frequencies().get(character, (None, None))
