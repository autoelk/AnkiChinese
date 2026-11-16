"""The shared workflow used by the CLI and GUI."""
from dataclasses import dataclass, replace
from typing import Optional
from .anki_connect import AnkiConnect
from .anki_sync import UpdatePlan, prepare_update, apply_update
from .config import RunRequest, normalize_characters
from .models import ProgressEvent, ignore_progress
from .export import write_csv, write_deck
from .sources import default_sources
from .selection import load_preferences, select_card
from .definitions import load_compact_glosses


def build_cards(characters, options, sources, report=ignore_progress):
    report(ProgressEvent("content", message="Loading dictionary and frequency data"))
    scores = sources.frequency.load_word_scores()
    dialogue_loader = getattr(sources.frequency, "load_dialogue_word_scores", None)
    dialogue_scores = dialogue_loader() if dialogue_loader else {}
    internet_loader = getattr(sources.frequency, "load_internet_word_scores", None)
    internet_scores = internet_loader() if internet_loader else {}
    preferences = load_preferences()
    compact_glosses = load_compact_glosses()
    cards, issues = [], []
    for index, character in enumerate(characters, 1):
        entries = sources.dictionary.lookup(character, scores)
        if dialogue_loader:
            entries = replace(entries, dialogue_frequencies={word: dialogue_scores[word]
                              for word, _, _ in entries.words if word in dialogue_scores})
        if internet_loader:
            entries = replace(entries, internet_frequencies={word: internet_scores[word]
                              for word, _, _ in entries.words if word in internet_scores})
        card = select_card(entries, options, preferences, compact_glosses)
        issues.extend(character + ": " + warning for warning in card.selection_warnings)
        if not card.definitions:
            issues.append(character + ": No usable dictionary entry")
        else:
            rank, per_million = sources.frequency.character_frequency(character)
            cards.append(replace(card, formation=sources.formation.formation(character) if sources.formation else "",
                                 hsk_level=sources.levels.level(character) if sources.levels else "", frequency_rank=rank,
                                 frequency_per_million=per_million))
        report(ProgressEvent("content", index, len(characters), "Selecting card content"))
    for card in cards:
        for message in card.selection_info:
            report(ProgressEvent("info", message="Info · " + card.character + ": " + message))
    return cards, issues


def prepare_audio(run, source, report=ignore_progress):
    options = run.request.options
    readings = [card.readings[0] if card.readings else "" for card in run.cards]
    audio_paths = {}
    unavailable = []
    total = len(set(readings) - {""})
    report(ProgressEvent("audio", 0, total, "Preparing audio recordings"))
    outcomes = source.get_recordings(dict.fromkeys(filter(None, readings)), options.audio_concurrency, options.audio_per_second)
    for completed, (reading, path, error) in enumerate(outcomes, 1):
        audio_paths[reading] = path
        if error == "No recording available":
            unavailable.append(reading)
        elif error:
            run.issues.append("{}: {}".format(reading, error))
        report(ProgressEvent("audio", completed, total, "Preparing audio recordings"))
    run.cards = [replace(card, audio_path=audio_paths.get(reading)) for card, reading in zip(run.cards, readings)]
    for reading in unavailable:
        report(ProgressEvent("info", message="Info · " + reading + ": No recording in the configured audio sources"))


@dataclass
class Run:
    request: RunRequest
    cards: list
    issues: list
    notice_paths: tuple = ()
    plan: Optional[UpdatePlan] = None


class Application:
    def __init__(self, anki=None, sources=None):
        self.anki = anki
        self.sources = sources

    def close(self):
        if self.anki is not None:
            self.anki.close()
            self.anki = None

    def prepare(self, request, report=ignore_progress):
        sources = self.sources or default_sources(request.options.audio_cache_dir)
        characters = request.characters
        if request.mode == "update":
            self.anki = self.anki or AnkiConnect()
            fields = self.anki.model_fields(request.model_name)
            if "Hanzi" not in fields:
                raise ValueError("Selected note type must contain a Hanzi field")
            if request.include_existing:
                notes = self.anki.notes(request.deck_name, request.model_name)
                characters = normalize_characters((*characters, *(note["fields"].get("Hanzi", "") for note in notes)))
        if not characters:
            raise ValueError("No Hanzi found")
        cards, issues = build_cards(characters, request.options, sources, report)
        run = Run(request, cards, issues, sources.notice_paths)
        if not run.cards:
            raise ValueError("No cards could be built from the supplied characters")
        if sources.audio is not None and (request.mode != "update" or "Audio" in fields):
            prepare_audio(run, sources.audio, report)
            run.notice_paths = sources.notice_paths
        for issue in run.issues:
            report(ProgressEvent("issue", message=issue))
        if request.mode == "update":
            report(ProgressEvent("plan", message="Preparing Anki update preview"))
            run.plan = prepare_update(run.cards, self.anki, request.deck_name, request.model_name, run.notice_paths)
        return run

    def apply(self, run, report=ignore_progress):
        request = run.request
        if request.mode == "update":
            updated, added = apply_update(run.plan, self.anki, report)
            report(ProgressEvent("result", message="Updated {} notes and added {} notes".format(updated, added)))
        else:
            report(ProgressEvent("export", message="Writing " + str(request.output_path)))
            writer = write_csv if request.mode == "csv" else write_deck
            writer(run.cards, request.output_path, run.notice_paths)
            report(ProgressEvent("result", message="Wrote " + str(request.output_path)))
            if request.mode == "anki":
                for name, cards in (
                    ("Writing", run.cards), ("Simplified Reading", run.cards),
                    ("Traditional Reading", [card for card in run.cards if card.traditional]),
                ):
                    report(ProgressEvent("result", message="{}: {} card(s) — {}".format(name, len(cards), " ".join(card.character for card in cards) or "none")))
        report(ProgressEvent("done", 1, 1, "Finished: {} characters, {} issue(s)".format(len(run.cards), len(run.issues))))
        return run
