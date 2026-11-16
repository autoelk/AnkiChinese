"""Read-only update planning and explicit, progress-reporting execution."""
import base64
import tempfile
from dataclasses import dataclass
from pathlib import Path
from .anki_connect import AnkiConnectError
from .export import write_additions_package
from .models import ProgressEvent, ignore_progress
from .rendering import NOTE_FIELDS, render_fields

@dataclass(frozen=True)
class ModelSnapshot:
    name: str
    field_names: tuple
    model_id: int = 0
    templates: tuple = ()
    css: str = ""

@dataclass(frozen=True)
class NoteChange:
    note_id: int
    character: str
    fields: dict
    expected_fields: dict

@dataclass(frozen=True)
class UpdatePlan:
    deck_name: str
    deck_id: int
    model: ModelSnapshot
    updates: tuple
    additions: tuple
    media_paths: tuple
    unchanged: int

    @property
    def has_changes(self):
        return bool(self.updates or self.additions)

    def summary(self):
        return ("Update {} / {}: {} notes to update, {} to add, {} unchanged, {} media files".format(
            self.deck_name, self.model.name, len(self.updates), len(self.additions), self.unchanged, len(self.media_paths)))

def prepare_update(cards, anki, deck_name, model_name, notice_paths=()):
    notes = anki.notes(deck_name, model_name)
    fields = tuple(anki.model_fields(model_name))
    if "Hanzi" not in fields:
        raise ValueError("Selected note type must contain a Hanzi field")
    supported_fields = [field for field in fields if field in NOTE_FIELDS]
    notes_by_character = {}
    for note in notes:
        character = note["fields"].get("Hanzi", "").strip()
        notes_by_character.setdefault(character, []).append(note)
    updates, additions, unchanged = [], [], 0
    seen = set()
    for card in cards:
        if card.character in seen:
            raise ValueError("Duplicate generated character: " + card.character)
        seen.add(card.character)
        values = render_fields(card)
        existing = notes_by_character.get(card.character, [])
        if not existing:
            additions.append({field: values.get(field, "") for field in fields})
        for note in existing:
            changed = {field: values[field] for field in supported_fields
                       if note["fields"].get(field, "") != values[field]}
            if changed:
                expected = {field: note["fields"].get(field, "") for field in (*changed, "Hanzi")}
                updates.append(NoteChange(note["noteId"], card.character, changed, expected))
            else:
                unchanged += 1
    snapshot = ModelSnapshot(model_name, fields)
    deck_id = 0
    if additions:
        model_id = anki.model_ids().get(model_name)
        deck_id = anki.deck_ids().get(deck_name)
        templates = anki.model_templates(model_name)
        if model_id is None or deck_id is None or not templates:
            raise ValueError("Could not read the selected Anki deck and note type for package import")
        snapshot = ModelSnapshot(model_name, fields, model_id,
                                 tuple((name, value.get("Front", ""), value.get("Back", "")) for name, value in templates.items()),
                                 anki.model_styling(model_name).get("css", ""))
    media_by_name = {}
    if updates or additions:
        media_by_name = {path.name: path for path in notice_paths}
        audio_characters = {change.character for change in updates if "Audio" in change.fields}
        if "Audio" in fields:
            audio_characters.update(values["Hanzi"] for values in additions)
        for card in cards:
            if card.character in audio_characters and card.audio_path:
                media_by_name[card.audio_path.name] = card.audio_path
        for path in media_by_name.values():
            if not path.is_file():
                raise ValueError("Missing media file: " + str(path))
    return UpdatePlan(deck_name, deck_id, snapshot, tuple(updates), tuple(additions),
                      tuple(path for _, path in sorted(media_by_name.items())), unchanged)



def _validate_current(plan, anki):
    if tuple(anki.model_fields(plan.model.name)) != plan.model.field_names:
        raise ValueError("The note type changed after the preview; prepare the update again")
    current_notes = {note["noteId"]: note for note in anki.notes(plan.deck_name, plan.model.name)}
    for change in plan.updates:
        note = current_notes.get(change.note_id)
        if note is None or any(note["fields"].get(name, "") != expected
                               for name, expected in change.expected_fields.items()):
            raise ValueError("Note {} changed after the preview; prepare the update again".format(change.character))
    existing = {note["fields"].get("Hanzi", "").strip() for note in current_notes.values()}
    if any(fields["Hanzi"] in existing for fields in plan.additions):
        raise ValueError("A planned new character was added after the preview; prepare the update again")
    if plan.additions:
        templates = tuple((name, value.get("Front", ""), value.get("Back", ""))
                          for name, value in anki.model_templates(plan.model.name).items())
        if (anki.model_ids().get(plan.model.name) != plan.model.model_id or anki.deck_ids().get(plan.deck_name) != plan.deck_id
                or templates != plan.model.templates or anki.model_styling(plan.model.name).get("css", "") != plan.model.css):
            raise ValueError("The deck or note templates changed after the preview; prepare the update again")


def apply_update(plan, anki, report=ignore_progress):
    if not plan.has_changes:
        return 0, 0
    _validate_current(plan, anki)
    updated = added = media_uploaded = 0
    # Build the package before making collection changes, and always clean it up.
    with tempfile.TemporaryDirectory(prefix="ankichinese_update_") as directory:
        package_path = Path(directory) / "additions.apkg"
        if plan.additions:
            write_additions_package(plan, package_path)
        try:
            for index, path in enumerate(plan.media_paths, 1):
                anki.invoke("storeMediaFile", filename=path.name,
                            data=base64.b64encode(path.read_bytes()).decode("ascii"))
                media_uploaded += 1
                report(ProgressEvent("upload", index, len(plan.media_paths), "Uploading media"))
            for index, change in enumerate(plan.updates, 1):
                anki.invoke("updateNoteFields", note={"id": change.note_id, "fields": change.fields})
                updated += 1
                report(ProgressEvent("update", index, len(plan.updates), "Applying note updates"))
            if plan.additions:
                report(ProgressEvent("import", 0, len(plan.additions), "Importing new notes"))
                if anki.invoke("importPackage", path=str(package_path)) is False:
                    raise ValueError("AnkiConnect could not import the additions package")
                imported = anki.notes(plan.deck_name, plan.model.name)
                verified = {note["fields"].get("Hanzi", "") for note in imported if note.get("cards")}
                expected = {fields["Hanzi"] for fields in plan.additions}
                added = len(expected & verified)
                if expected - verified:
                    raise ValueError("Could not verify imported characters: " + " ".join(sorted(expected - verified)))
                report(ProgressEvent("import", added, len(plan.additions), "Imported new notes"))
        except (AnkiConnectError, OSError, ValueError) as exc:
            raise AnkiConnectError(
                "Anki update stopped after {} updated notes, {} added notes and {} media uploads. "
                "Partial changes may be present. {}".format(updated, added, media_uploaded, exc)
            ) from exc
    return updated, added
