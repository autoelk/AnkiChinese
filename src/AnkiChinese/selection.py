"""Learning policy over normalized entries, with editable selection preferences."""
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .models import Card, ExampleWord
from .definitions import load_compact_glosses


# Frequency thresholds are occurrences per million words in the named corpus.
# The sample review retains everyday readings with relatively sparse compounds, such as 薄 bao2.
MIN_READING_WORD_FREQUENCY_PER_MILLION = 0.25
MIN_NAME_DIALOGUE_FREQUENCY_PER_MILLION = 2.0
MIN_NAME_INTERNET_FREQUENCY_PER_MILLION = 2.0
MIN_NEEDED_NAME_FREQUENCY_PER_MILLION = 0.25
NAME_FREQUENCY_MULTIPLIER = 0.5
FORMAL_FREQUENCY_MULTIPLIER = 0.7
OVERLAPPING_MEANING_MULTIPLIER = 0.7
MAX_NAMES_PER_CARD = 1
DEFINITION_SIMILARITY_THRESHOLD = 0.8
DEFAULT_PREFERENCES_PATH = Path(__file__).resolve().parent / "data" / "selection_preferences.json"


@dataclass(frozen=True)
class SelectionPreferences:
    preferred_words: frozenset = frozenset()
    excluded_words: frozenset = frozenset()
    preferred_names: frozenset = frozenset()
    included_readings: dict = field(default_factory=dict)
    excluded_readings: dict = field(default_factory=dict)


def load_preferences(path=DEFAULT_PREFERENCES_PATH):
    """Read once per generation so edits take effect on the next run."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Selection preferences must be a JSON object")
    unknown = set(data) - set(SelectionPreferences.__dataclass_fields__)
    if unknown:
        raise ValueError("Unknown selection preferences: " + ", ".join(sorted(unknown)))
    values = {}
    for name in ("preferred_words", "excluded_words", "preferred_names"):
        words = data.get(name, [])
        if not isinstance(words, list) or any(not isinstance(word, str) or not word for word in words):
            raise ValueError(name + " must be a list of nonempty words")
        values[name] = frozenset(words)
    for name in ("included_readings", "excluded_readings"):
        readings = data.get(name, {})
        if not isinstance(readings, dict):
            raise ValueError(name + " must map characters to lists of tone-number pinyin readings")
        values[name] = {}
        for character, options in readings.items():
            if len(character) != 1 or not isinstance(options, list) or any(
                not isinstance(reading, str) or not re.fullmatch(r"[a-züv:]+[1-5]", reading) for reading in options
            ):
                raise ValueError(name + " must map characters to lists such as [\"xing2\", \"hang2\"]")
            values[name][character] = tuple(dict.fromkeys(options))
    if values["excluded_words"] & (values["preferred_words"] | values["preferred_names"]):
        raise ValueError("A preferred word or name cannot also be excluded")
    for character, readings in values["included_readings"].items():
        if set(readings) & set(values["excluded_readings"].get(character, ())):
            raise ValueError("A reading cannot be both included and excluded for " + character)
    return SelectionPreferences(**values)


def definition_tokens(text):
    return {token for token in re.findall(r"[a-z]+", text.lower()) if len(token) > 2} - {
        "the", "one", "than", "for", "and", "with", "from", "etc", "sth", "someone", "something",
    }


def similar_definitions(left, right):
    left_tokens, right_tokens = definition_tokens(left), definition_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
    return overlap >= DEFINITION_SIMILARITY_THRESHOLD


def target_readings(character, word, pronunciation):
    return {pronunciation[i] for i, char in enumerate(word) if char == character}


@dataclass(frozen=True)
class Candidate:
    example: ExampleWord
    readings: frozenset
    frequency: float
    is_name: bool
    is_preferred: bool
    is_formal: bool
    unambiguous: bool
    frequency_missing: bool
    is_usage: bool = False

    @property
    def score(self):
        frequency = self.frequency
        if self.is_name and not self.is_preferred:
            frequency *= NAME_FREQUENCY_MULTIPLIER
        if self.is_formal:
            frequency *= FORMAL_FREQUENCY_MULTIPLIER
        return math.log1p(frequency)


def collect_candidates(character_entries, preferences, definition_limit):
    candidates = []
    excluded_readings = set(preferences.excluded_readings.get(character_entries.character, ()))
    has_ordinary_examples = any(
        len(word) > 1 and word not in preferences.excluded_words
        and frequency >= MIN_READING_WORD_FREQUENCY_PER_MILLION
        and any(not meaning.is_name and not meaning.is_rare for entry in entries for meaning in entry.meanings)
        for word, entries, frequency in character_entries.words
    )
    for word, entries, frequency in character_entries.words:
        if len(word) < 2 or word in preferences.excluded_words:
            continue
        valid_entries = [entry for entry in entries if len(entry.pronunciation) == len(word) and entry.meanings]
        # A written word's frequency is shared by all its dictionary readings.
        word_readings = set().union(*(target_readings(character_entries.character, word, entry.pronunciation)
                                     for entry in valid_entries))
        meanings_by_pronunciation = defaultdict(list)
        for entry in valid_entries:
            meanings_by_pronunciation[entry.pronunciation].extend(entry.meanings)
        preferred = word in preferences.preferred_words or word in preferences.preferred_names
        for pronunciation, meanings in meanings_by_pronunciation.items():
            readings = target_readings(character_entries.character, word, pronunciation)
            if readings & excluded_readings:
                continue
            usable = [meaning for meaning in meanings if preferred or not meaning.is_rare]
            if not usable:
                continue
            usable.sort(key=lambda meaning: (meaning.is_name, meaning.is_rare, meaning.is_formal))
            is_name = usable[0].is_name
            dialogue_frequency = character_entries.dialogue_frequencies.get(word, 0)
            internet_frequency = character_entries.internet_frequencies.get(word, 0)
            name_is_frequent = (dialogue_frequency >= MIN_NAME_DIALOGUE_FREQUENCY_PER_MILLION
                                or internet_frequency >= MIN_NAME_INTERNET_FREQUENCY_PER_MILLION
                                or (not has_ordinary_examples and frequency >= MIN_NEEDED_NAME_FREQUENCY_PER_MILLION))
            if is_name and not preferred and not name_is_frequent:
                continue
            definitions = []
            chosen_meanings = [meaning for meaning in usable if meaning.is_name == is_name]
            for meaning in chosen_meanings:
                if not any(similar_definitions(meaning.definition, other) for other in definitions):
                    definitions.append(meaning.definition)
            example = ExampleWord(word, pronunciation, tuple(definitions[:definition_limit]))
            candidates.append(Candidate(example, frozenset(readings), max(frequency, 0), is_name, preferred,
                                        all(meaning.is_formal for meaning in chosen_meanings),
                                        len(word_readings) == 1, word in character_entries.missing_word_frequencies))
    for example in character_entries.usage_examples:
        readings = target_readings(character_entries.character, example.word, example.pronunciation)
        if example.word not in preferences.excluded_words and not readings & excluded_readings:
            preferred = example.word in preferences.preferred_words
            candidates.append(Candidate(example, frozenset(readings), 0, False, preferred, False, True, True, True))
    return sorted(candidates, key=lambda candidate: (
        -candidate.score, candidate.example.word, candidate.example.pronunciation,
    ))


def choose_readings(character_entries, candidates=None, preferences=None):
    preferences = preferences or SelectionPreferences()
    if candidates is None:
        candidates = collect_candidates(character_entries, preferences, 3)
    priorities = {}
    for entry in character_entries.entries:
        if not entry.pronunciation:
            continue
        rank = min(((meaning.is_rare, meaning.is_name, meaning.is_formal)
                    for meaning in entry.meanings), default=(True, True, True))
        reading = entry.pronunciation[0]
        priorities[reading] = min(priorities.get(reading, rank), rank)
    strongest = defaultdict(float)
    preferred_readings = set(preferences.included_readings.get(character_entries.character, ()))
    known_readings = set(priorities) | {reading for candidate in candidates for reading in candidate.readings}
    unknown = preferred_readings - known_readings
    if unknown:
        raise ValueError("Unknown included reading for " + character_entries.character + ": " + ", ".join(sorted(unknown)))
    for candidate in candidates:
        if candidate.is_preferred and candidate.unambiguous:
            preferred_readings.update(candidate.readings)
        # Names reach this point after passing a source threshold or an override.
        if candidate.unambiguous:
            for reading in candidate.readings:
                strongest[reading] = max(strongest[reading], candidate.frequency)
    eligible = {reading for reading in known_readings if strongest[reading] >= MIN_READING_WORD_FREQUENCY_PER_MILLION}
    eligible.update(reading for candidate in candidates if candidate.is_usage for reading in candidate.readings)
    eligible.update(preferred_readings)
    excluded = set(preferences.excluded_readings.get(character_entries.character, ()))
    eligible -= excluded
    # Standalone pronunciation comes from the character entry. Compound-only
    # neutral readings retain their place in examples, after the standalone reading.
    available = [reading for reading in priorities if reading not in excluded]
    dictionary_order = {reading: index for index, reading in enumerate(priorities)}
    primary = character_entries.preferred_reading
    if primary not in available:
        primary = min(available, key=lambda reading: (
            reading.endswith("5") and any(other[:-1] == reading[:-1] and not other.endswith("5") for other in available),
            reading not in eligible, priorities[reading],
            -strongest[reading], dictionary_order[reading],
        ), default="")
    if primary:
        eligible.add(primary)
    eligible -= excluded
    return tuple(sorted(eligible, key=lambda reading: (
        reading != primary,
        reading not in preferred_readings, -strongest[reading],
        priorities.get(reading, (False, False, False)), reading,
    )))


def choose_definitions(character_entries, readings, limit, compact_glosses=None):
    compact_glosses = compact_glosses if compact_glosses is not None else load_compact_glosses()
    meanings_by_reading = defaultdict(list)
    for entry in character_entries.entries:
        if entry.pronunciation:
            meanings_by_reading[entry.pronunciation[0]].extend(entry.meanings)
    glosses_by_reading = []
    reviewed = compact_glosses.get(character_entries.character, {})
    for reading in readings:
        override = reviewed.get(reading)
        if override:
            glosses = override["glosses"]
        else:
            # Stable sorting preserves dictionary order within each usage category.
            meanings = sorted(meanings_by_reading[reading], key=lambda meaning: (meaning.is_rare, meaning.is_name))
            glosses = []
            for meaning in meanings:
                gloss = re.sub(r"^to\s+", "", meaning.definition)
                if meaning.is_rare:
                    gloss += " (archaic/historical)"
                elif meaning.is_formal:
                    gloss += " (formal)"
                glosses.append(gloss)
        glosses_by_reading.append(tuple(dict.fromkeys(glosses)))
    # Give each reading a gloss before adding more senses in reviewed/dictionary order.
    definitions = []
    for index in range(max((len(glosses) for glosses in glosses_by_reading), default=0)):
        for glosses in glosses_by_reading:
            if index < len(glosses) and glosses[index] not in definitions:
                definitions.append(glosses[index])
            if len(definitions) >= limit:
                return tuple(definitions)
    return tuple(definitions[:limit]) or ((character_entries.fallback_definition,) if character_entries.fallback_definition else ())


def choose_examples(character_entries, readings, limit, definition_limit, candidates=None, preferences=None, notes=None, warnings=None, info=None):
    preferences = preferences or SelectionPreferences()
    notes = notes if notes is not None else []
    warnings = warnings if warnings is not None else []
    info = info if info is not None else []
    if candidates is None:
        candidates = collect_candidates(character_entries, preferences, definition_limit)
    candidates = [candidate for candidate in candidates if candidate.readings <= set(readings)]
    selected = []
    selected_words = set()

    def add(candidate, reason):
        selected.append(candidate)
        selected_words.add(candidate.example.word)
        details = [reason]
        if candidate.is_usage:
            details.append("reviewed usage phrase, frequency unmeasured")
        else:
            details.append("{:.2f} per million".format(candidate.frequency))
        if candidate.is_name:
            details.append("name")
        internet_frequency = character_entries.internet_frequencies.get(candidate.example.word)
        if internet_frequency is not None:
            details.append("Weibo {:.2f} per million".format(internet_frequency))
        if candidate.frequency_missing and not candidate.is_usage:
            details.append("frequency missing")
        if not candidate.unambiguous:
            details.append("written frequency shared across readings")
        notes.append(candidate.example.word + ": " + "; ".join(details))

    forced = set(preferences.included_readings.get(character_entries.character, ()))
    preferred = {reading for candidate in candidates if candidate.is_preferred and candidate.unambiguous
                 for reading in candidate.readings}
    reading_order = {reading: index for index, reading in enumerate(readings)}
    covered_first = sorted(readings, key=lambda reading: (
        reading not in forced | preferred, reading_order[reading],
    ))[:limit]
    coverage_order = sorted(covered_first, key=lambda reading: (
        sum(reading in candidate.readings for candidate in candidates), reading_order[reading],
    ))
    for reading in coverage_order:
        if any(reading in candidate.readings for candidate in selected):
            continue
        matches = [candidate for candidate in candidates
                   if reading in candidate.readings and candidate.example.word not in selected_words]
        if sum(candidate.is_name for candidate in selected) >= MAX_NAMES_PER_CARD:
            ordinary = [candidate for candidate in matches if not candidate.is_name]
            matches = ordinary or matches
        if matches:
            candidate = max(matches, key=lambda candidate: (candidate.is_preferred, candidate.score))
            add(candidate, "covers " + reading)
    for candidate in sorted(candidates, key=lambda candidate: (not candidate.is_preferred, -candidate.score)):
        if len(selected) >= limit or not candidate.is_preferred:
            break
        if candidate.example.word not in selected_words:
            add(candidate, "preferred word or name")

    def variety_score(candidate):
        overlap = any(similar_definitions(definition, other)
                      for definition in candidate.example.definitions
                      for chosen in selected for other in chosen.example.definitions)
        return candidate.score * (OVERLAPPING_MEANING_MULTIPLIER if overlap else 1.0)

    name_only = bool(character_entries.entries) and all(
        meaning.is_name for entry in character_entries.entries for meaning in entry.meanings
    )
    while len(selected) < limit:
        name_count = sum(candidate.is_name for candidate in selected)
        available = [candidate for candidate in candidates if candidate.example.word not in selected_words
                     and (not candidate.is_name or name_count < MAX_NAMES_PER_CARD or name_only)]
        if not available:
            break
        candidate = max(available, key=variety_score)
        add(candidate, "frequency and meaning variety")
    covered = {reading for candidate in selected for reading in candidate.readings}
    for reading in readings:
        if reading not in covered:
            if any(reading in candidate.readings for candidate in candidates):
                warnings.append("Example coverage incomplete for " + reading)
            else:
                info.append("No suitable compound or usage phrase for " + reading)
    for word in sorted(preferences.preferred_words | preferences.preferred_names):
        if character_entries.character in word and word not in selected_words:
            warnings.append("Preferred example unavailable or exceeds example limit: " + word)
    return tuple(candidate.example for candidate in selected)


def select_card(character_entries, options, preferences=None, compact_glosses=None):
    preferences = preferences if preferences is not None else load_preferences()
    candidates = collect_candidates(character_entries, preferences, options.definition_limit)
    readings = choose_readings(character_entries, candidates, preferences)
    notes, warnings, info = [], [], []
    examples = choose_examples(character_entries, readings, options.example_limit, options.definition_limit,
                               candidates, preferences, notes, warnings, info)
    if not readings:
        warnings.append("No usable reading remains after reading exclusions")
    return Card(character_entries.character, character_entries.traditional, readings,
                choose_definitions(character_entries, readings, options.definition_limit, compact_glosses), examples,
                selection_notes=tuple(notes), selection_warnings=tuple(warnings), selection_info=tuple(info))
