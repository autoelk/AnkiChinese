"""Editable blend of spoken dialogue, social media, and news word frequencies."""
from collections import defaultdict
from functools import lru_cache

from . import bcc, leiden_weibo


# Weights sum to one. Each source supplies occurrences per million words.
DIALOGUE_WEIGHT = 0.50
INTERNET_WEIGHT = 0.30
NEWS_WEIGHT = 0.20
NOTICE_PATHS = bcc.NOTICE_PATHS + leiden_weibo.NOTICE_PATHS


@lru_cache(maxsize=1)
def load_word_scores():
    weights = (DIALOGUE_WEIGHT, INTERNET_WEIGHT, NEWS_WEIGHT)
    if any(weight < 0 for weight in weights) or abs(sum(weights) - 1.0) > 1e-9:
        raise ValueError("Word frequency weights must be nonnegative and sum to one")
    scores = defaultdict(float)
    loaders = (
        (DIALOGUE_WEIGHT, bcc.load_dialogue_word_scores),
        (INTERNET_WEIGHT, leiden_weibo.load_word_scores),
        (NEWS_WEIGHT, bcc.load_news_word_scores),
    )
    for weight, loader in loaders:
        if weight:
            for word, frequency in loader().items():
                scores[word] += weight * frequency
    return dict(scores)


def load_dialogue_word_scores():
    return bcc.load_dialogue_word_scores()


def load_internet_word_scores():
    return leiden_weibo.load_word_scores() if INTERNET_WEIGHT else {}


def character_frequency(character):
    return bcc.character_frequency(character)
