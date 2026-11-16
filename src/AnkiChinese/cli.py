"""Command-line frontend for the shared application workflow."""
import argparse
from pathlib import Path

# Support running this file directly from a source checkout.
if __name__ == "__main__" and not __package__:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "AnkiChinese"

from tqdm import tqdm
from .anki_connect import AnkiConnect, AnkiConnectError
from .application import Application
from .config import GenerationOptions, RunRequest
from .rendering import NOTE_FIELDS


class ConsoleProgress:
    def __init__(self):
        self.bar = None
        self.phase = None

    def close(self):
        if self.bar:
            self.bar.close()
            self.bar = None

    def __call__(self, event):
        if event.phase != self.phase:
            self.close()
            self.phase = event.phase
        if event.total and event.phase != "done":
            if self.bar is None:
                self.bar = tqdm(total=event.total, desc=event.message)
            self.bar.update(event.completed - self.bar.n)
        elif event.message:
            print(event.message)


def choose(label, choices, provided=None):
    if provided:
        if provided not in choices:
            raise ValueError("Unknown {}: {}".format(label, provided))
        return provided
    if not choices:
        raise ValueError("No available " + label)
    if len(choices) == 1:
        print(label + ": " + choices[0])
        return choices[0]
    print(label + ": " + ", ".join(choices))
    while True:
        selected = input("Choose " + label + ": ").strip()
        if selected in choices:
            return selected


def confirm(message):
    return input(message + " [y/n] ").strip().lower() in ("y", "yes")


def cli(argv=None):
    defaults = GenerationOptions()
    parser = argparse.ArgumentParser(description="Generate Chinese character flashcards for Anki")
    parser.add_argument("--export", "-x", choices=("anki", "csv", "update"), default="anki")
    parser.add_argument("--input", "-i", default="input.txt")
    parser.add_argument("--output", "-o", dest="output_path", default="ankichinese_output", help="Output name, with or without extension")
    parser.add_argument("--definitions", "-def", dest="definition_limit", type=int, default=defaults.definition_limit)
    parser.add_argument("--examples", "-ex", dest="example_limit", type=int, default=defaults.example_limit)
    parser.add_argument("--audio-downloads-at-once", dest="audio_concurrency", type=int, default=defaults.audio_concurrency)
    parser.add_argument("--audio-downloads-per-second", dest="audio_per_second", type=int, default=defaults.audio_per_second)
    parser.add_argument("--audio-cache", dest="audio_cache_dir", type=Path, default=defaults.audio_cache_dir)
    parser.add_argument("--deck", dest="deck_name", help="Deck to update")
    parser.add_argument("--model", dest="model_name", help="Note type to update")
    parser.add_argument("--include-existing", action="store_true", default=None, help="Also regenerate existing deck characters")
    args = parser.parse_args(argv)
    progress = ConsoleProgress()
    anki = None
    try:
        options = GenerationOptions(args.definition_limit, args.example_limit, args.audio_concurrency,
                                  args.audio_per_second, args.audio_cache_dir)
        characters = Path(args.input).read_text(encoding="utf-8")
        deck_name = model_name = ""
        include_existing = False
        if args.export == "update":
            anki = AnkiConnect()
            deck_name = choose("deck", anki.decks(), args.deck_name)
            models = [name for name in anki.models() if "Hanzi" in anki.model_fields(name)]
            model_name = choose("note type", models, args.model_name)
            print("Fields managed by AnkiChinese: " + ", ".join(name for name in anki.model_fields(model_name) if name in NOTE_FIELDS))
            include_existing = args.include_existing if args.include_existing is not None else confirm("Also process the deck's existing characters?")
        request = RunRequest(characters, args.export, options, Path(args.output_path), deck_name, model_name, include_existing)
        app = Application(anki=anki)
        run = app.prepare(request, progress)
        progress.close()
        if run.plan:
            print(run.plan.summary())
            if run.plan.has_changes and not confirm("Apply these changes to Anki?"):
                print("Update canceled")
                return 0
        app.apply(run, progress)
        return 0
    except (ValueError, OSError, AnkiConnectError) as exc:
        print(str(exc))
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Any confirmed Anki changes remain applied.")
        return 130
    finally:
        progress.close()
        if anki is not None:
            anki.close()


if __name__ == "__main__":
    raise SystemExit(cli())
