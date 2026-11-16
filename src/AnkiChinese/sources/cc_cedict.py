from functools import lru_cache
from pathlib import Path
import json
import re
from collections import defaultdict

from ..models import DictionaryEntry, CharacterEntries, ExampleWord, Meaning
from ..config import is_hanzi


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

NOTICE_PATHS = (Path(DATA_DIR) / 'CC_CEDICT_NOTICE.txt',)

_LABELS = {
    "bound form", "idiom", "fig.", "lit.", "lit. and fig.", "coll.",
    "slang", "internet slang", "tw", "prc", "hk", "cantonese", "dialect",
    "literary", "old", "archaic", "historical", "formal", "vulgar", "derog.",
    "onom.", "math.", "physics", "chemistry", "computing", "medicine",
    "botany", "zoology", "music", "law", "finance", "buddhism", "tcm",
    "grammar", "attributive", "name", "surname", "loanword", "neologism",
}


def _strip_labels(definition: str) -> str:
    text = definition.strip()
    while True:
        match = re.match(r"^\(([^()]*)\)\s*", text)
        if not match or match[1].lower() not in _LABELS:
            break
        text = text[match.end():]
    if re.fullmatch(r"\([^()]+\)", text):
        text = text[1:-1].strip()
    return text


def _contains_hanzi(text: str) -> bool:
    return any(is_hanzi(char) for char in text)


def _remove_hanzi_parenthetical_notes(text: str) -> str:
    """Remove balanced parenthetical notes that contain Hanzi."""
    result = []
    depth = 0
    note_start = 0
    text_start = 0

    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                note_start = index
            depth += 1
        elif char == ")" and depth:
            depth -= 1
            if depth == 0:
                note = text[note_start : index + 1]
                if _contains_hanzi(note):
                    result.append(text[text_start:note_start])
                    text_start = index + 1

    result.append(text[text_start:])
    return re.sub(r"\s+", " ", "".join(result)).strip()


def _clean_definition(definition: str) -> str:
    """Keep only English that is safe to show on a writing prompt."""
    cleaned_definition = _remove_hanzi_parenthetical_notes(_strip_labels(definition))
    note_match = re.match(
        r"^(?:see(?: also)?\s+|(?:\w+\s+)?variant of\s+|also pr\.|abbr\. for\s+|used\s+(?:(?:in|after|before|with)\b|(?=[\u3400-\u9fff])))",
        _strip_labels(cleaned_definition), re.IGNORECASE,
    )
    if note_match:
        return ""
    # Keep English place descriptions while removing linked Chinese cross-references.
    cleaned_definition = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+(?:\|[\u3400-\u9fff\uf900-\ufaff]+)?\[[^\]]*\]", "", cleaned_definition)
    cleaned_definition = re.sub(r"\s+", " ", cleaned_definition).strip(" ,;")
    if len(cleaned_definition) > 160 or _contains_hanzi(cleaned_definition):
        return ""
    return cleaned_definition


def _is_name_definition(definition: str) -> bool:
    lowered = definition.lower()
    return any(
        phrase in lowered
        for phrase in (
            "surname", "given name", "family name", "place name", "(name)",
            "person name", "company name", "brand name", "trade name", "short name",
            "male name", "female name", "feminine name", "biblical name", "used as a name",
            "name of ", "name for ", "nickname of ", "pen name", "personal name",
            "proper name", "proper noun",
        )
    ) or bool(re.search(r"\bused in (?:[\w'-]+ )*names\b", lowered))


def _parse_meanings(definitions, is_proper_name):
    is_old_variant = bool(re.match(r"^old variant of", definitions[0], re.IGNORECASE))
    meanings = []
    for definition in definitions:
        cleaned_definition = _clean_definition(definition)
        if cleaned_definition:
            is_name = is_proper_name or _is_name_definition(definition)
            is_rare = is_old_variant or bool(re.search(r"\((?:archaic|old|historical)\)", definition, re.IGNORECASE))
            is_formal = bool(re.search(r"\((?:literary|formal)\)", definition, re.IGNORECASE))
            meanings.append(Meaning(cleaned_definition, is_name, is_rare, is_formal))
    return tuple(meanings)


def _resolve_alias_meanings(entry, entries_by_word, visiting):
    """Follow dictionary references while keeping each written form's pronunciation."""
    parsed = entry["parsed_entry"]
    if parsed.meanings or id(entry) in visiting:
        return parsed.meanings
    visiting = visiting | {id(entry)}
    meanings = []
    for definition in entry["definitions"]:
        reference = re.fullmatch(r"(?:see|(?:old |archaic |ancient )?variant of) ([^\s\[]+)\[([^\]]+)\]", definition)
        if not reference:
            continue
        word = reference[1].split("|")[-1]
        pronunciation = tuple(token.lower() for token in reference[2].split())
        for target in entries_by_word.get(word, []):
            if target["parsed_entry"].pronunciation == pronunciation:
                for meaning in _resolve_alias_meanings(target, entries_by_word, visiting):
                    is_old = definition.startswith(("old variant", "archaic variant", "ancient variant"))
                    meanings.append(Meaning(meaning.definition, meaning.is_name or entry.get("is_proper_name", False),
                                            meaning.is_rare or is_old, meaning.is_formal))
    return tuple(dict.fromkeys(meanings))


@lru_cache(maxsize=1)
def _load_entries():
    """Parse entries once and index simplified words, traditional words and characters."""
    entries_by_word = defaultdict(list)
    entry_pattern = re.compile(r"^(\S+)\s+(\S+)\s+\[(.*?)\]\s+/(.*)/$")
    with (DATA_DIR / "cedict_ts.u8").open(encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = entry_pattern.match(line)
            if not match:
                continue
            traditional, simplified, pinyin, definitions = match.groups()
            definitions = definitions.strip("/").split("/")
            pronunciation = tuple(token.lower() for token in pinyin.split())
            is_proper_name = any(token[:1].isupper() for token in pinyin.split())
            entries_by_word[simplified].append({
                "traditional": traditional,
                "is_proper_name": is_proper_name,
                "definitions": definitions,
                "parsed_entry": DictionaryEntry(pronunciation, _parse_meanings(definitions, is_proper_name), tuple(definitions)),
            })

    for entries in entries_by_word.values():
        for entry in entries:
            parsed = entry["parsed_entry"]
            if not parsed.meanings:
                entry["parsed_entry"] = DictionaryEntry(parsed.pronunciation,
                    _resolve_alias_meanings(entry, entries_by_word, set()), parsed.source_definitions)

    words_by_character = defaultdict(list)
    entries_by_traditional = defaultdict(list)
    for word, entries in entries_by_word.items():
        for entry in entries:
            entries_by_traditional[entry["traditional"]].append(entry)
        for character in dict.fromkeys(word):
            words_by_character[character].append((word, entries))
        for traditional in dict.fromkeys(entry["traditional"] for entry in entries):
            for character in dict.fromkeys(traditional):
                if character not in word:
                    matching = [entry for entry in entries if entry["traditional"] == traditional]
                    words_by_character[character].append((traditional, matching))

    return entries_by_word, words_by_character, entries_by_traditional


def _fallback_definition(entries) -> str:
    """Describe dictionary-only character usage without exposing Hanzi."""
    definitions = [definition for entry in entries for definition in entry["definitions"]]
    for definition in definitions:
        # Geographic short names often provide their English name before a
        # Chinese cross-reference. Keep that English explanation.
        if re.match(r"^(?:short name|abbr\. for)", definition, re.IGNORECASE):
            prefix = re.split(r"[\u3400-\u9fff\uf900-\ufaff]", definition, maxsplit=1)[0].strip()
            if re.search(r"(?:for)\s+[A-Za-z]{2,}", prefix) and len(prefix) <= 100:
                return prefix
    if any("name" in definition.lower() for definition in definitions):
        return "used in names"
    if any("variant of" in definition.lower() for definition in definitions):
        return "variant form"
    if definitions:
        return "used in compounds"
    return ""


def _traditional_for_character(character, candidates, character_entries) -> str:
    votes = defaultdict(float)
    for word, word_entries, score in candidates:
        forms = {
            entry["traditional"][index]
            for entry in word_entries
            for index, char in enumerate(word)
            if char == character and index < len(entry["traditional"])
        }
        # A written word supplies one score, even if it has several entries.
        for form in sorted(forms):
            votes[form] += score / len(forms)
    if not votes:
        votes = {entry["traditional"]: 0 for entry in character_entries}
    if not votes:
        return ""
    # An unchanged form must be allowed to win; otherwise an uncommon variant
    # is always preferred over an identical simplified/traditional character.
    chosen = max(votes, key=lambda form: (votes[form], form == character))
    return "" if chosen == character else chosen


def lookup(character: str, word_scores: dict, dialogue_scores=None) -> CharacterEntries:
    """Interpret CC-CEDICT without choosing learning content or rendering HTML."""
    entries_by_word, words_by_character, entries_by_traditional = _load_entries()
    entries = entries_by_word.get(character) or entries_by_traditional.get(character, [])
    candidates = [(word, entries, word_scores.get(word, 0))
                  for word, entries in words_by_character.get(character, [])]
    usage = _load_character_usage().get(character, {})
    return CharacterEntries(
        character,
        tuple(entry["parsed_entry"] for entry in entries),
        tuple((word, tuple(entry["parsed_entry"] for entry in entries), score)
              for word, entries, score in candidates),
        _traditional_for_character(character, candidates, entries),
        _fallback_definition(entries),
        {word: dialogue_scores[word] for word, _, _ in candidates if word in (dialogue_scores or {})},
        frozenset(word for word, _, _ in candidates if word not in word_scores),
        preferred_reading=usage.get("reading", ""),
        usage_examples=tuple(ExampleWord(example["word"], tuple(example["pinyin"].split()),
                                        (example["definition"],)) for example in usage.get("examples", [])),
    )


@lru_cache(maxsize=1)
def _load_character_usage():
    """Reviewed short phrases for characters poorly represented by dictionary compounds."""
    return json.loads((DATA_DIR / "character_usage.json").read_text(encoding="utf-8"))
