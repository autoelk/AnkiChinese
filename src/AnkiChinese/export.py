"""Output files only. Collection synchronization lives in anki_sync."""
import csv
import shutil
from pathlib import Path
import genanki
from .rendering import NOTE_FIELDS, render_fields
PACKAGE_DIR = Path(__file__).resolve().parent

MODEL_ID = 1354988330
DECK_ID = 2085137232


def build_model():
    def read_template(path):
        return (PACKAGE_DIR / "card_template" / path).read_text(encoding="utf-8")
    return genanki.Model(
        MODEL_ID, "AnkiChinese", fields=[{"name": name} for name in NOTE_FIELDS],
        templates=[
            {"name": "AnkiChinese Writing", "qfmt": read_template("writing/front.html"), "afmt": read_template("writing/back.html")},
            {"name": "AnkiChinese Simplified Reading", "qfmt": read_template("reading/front.html"), "afmt": read_template("reading/back.html")},
            {"name": "AnkiChinese Traditional Reading", "qfmt": read_template("reading/traditional_front.html"), "afmt": read_template("reading/traditional_back.html")},
        ], css=read_template("styles.css"), sort_field_index=0,
    )


def write_csv(cards, output_path, notice_paths=()):
    output_path = Path(output_path)
    with output_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=NOTE_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(render_fields(card) for card in cards)
    for notice in notice_paths:
        shutil.copyfile(notice, output_path.with_suffix("." + notice.name))


def write_deck(cards, output_path, notice_paths=()):
    output_path = Path(output_path).resolve()
    model = build_model()
    deck = genanki.Deck(DECK_ID, output_path.stem, description=(
        "Chinese character flashcards. Data and audio credits and license notices "
        "for the sources used are included in the package media."
    ))
    media_by_name = {}
    for card in cards:
        fields = render_fields(card)
        deck.add_note(genanki.Note(model=model, fields=[fields[name] for name in NOTE_FIELDS],
                                  guid=genanki.guid_for(card.character)))
        if card.audio_path:
            media_by_name[card.audio_path.name] = card.audio_path
    package = genanki.Package(deck)
    package.media_files = [str(path) for _, path in sorted(media_by_name.items())]
    package.media_files.extend(str(path) for path in notice_paths)
    package.media_files.append(str((PACKAGE_DIR / "card_template/_CNstrokeorder.ttf")))
    package.write_to_file(str(output_path))


def write_additions_package(plan, output_path):
    """Preserve the selected collection's model ID, field order and templates."""
    snapshot = plan.model
    templates = [{"name": name, "qfmt": front, "afmt": back} for name, front, back in snapshot.templates]
    is_cloze = any("{{cloze:" in (t["qfmt"] + t["afmt"]).lower() for t in templates)
    model = genanki.Model(snapshot.model_id, snapshot.name, fields=[{"name": name} for name in snapshot.field_names],
                          templates=templates, css=snapshot.css, model_type=1 if is_cloze else 0)
    deck = genanki.Deck(plan.deck_id, plan.deck_name)
    for values in plan.additions:
        deck.add_note(genanki.Note(model=model, fields=[values.get(name, "") for name in snapshot.field_names],
                                  guid=genanki.guid_for(values["Hanzi"])))
    genanki.Package(deck).write_to_file(str(output_path))
