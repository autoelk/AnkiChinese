"""Offline BCC frequency estimates for characters and example words."""

import csv
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
SOURCES = (("dialogue", 0.7), ("multi_domain_total", 0.3))


def read_counts(path):
    """Read a complete published table, rejecting malformed packaged data."""
    counts = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            token = row["token"].strip()
            count = int(row["count"])
            if not token or count <= 0 or token in counts:
                raise ValueError("Invalid or duplicate frequency entry in {}".format(path))
            counts[token] = count
    if not counts:
        raise ValueError("Empty frequency table: {}".format(path))
    return counts


def blend_counts(sources):
    """Normalize each full table before weighting; missing entries contribute zero."""
    scores = {}
    for counts, weight in sources:
        total = sum(counts.values())
        if total <= 0:
            raise ValueError("Frequency totals must be positive")
        for token, count in counts.items():
            scores[token] = scores.get(token, 0.0) + weight * count / total * 1_000_000
    return scores


@lru_cache(maxsize=2)
def load_frequencies(kind):
    if kind not in {"char", "word"}:
        raise ValueError("Frequency kind must be 'char' or 'word'")
    return blend_counts(
        (read_counts(DATA_DIR / ("bcc_{}_{}_freq.txt".format(source, kind))), weight)
        for source, weight in SOURCES
    )


@lru_cache(maxsize=1)
def load_char_freq_map():
    """Return character -> (ordinal rank, blended occurrences per million)."""
    scores = load_frequencies("char")
    ordered = sorted(scores, key=lambda token: (-scores[token], token))
    return {token: (rank, scores[token]) for rank, token in enumerate(ordered, 1)}


def word_frequency(word):
    return load_frequencies("word").get(word.strip(), 0.0)
