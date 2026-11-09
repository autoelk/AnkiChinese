import genanki
import os
import pandas as pd
import re as regex
import base64
import tempfile

try:
    from .anki_connect import AnkiConnectError
except ImportError:
    from anki_connect import AnkiConnectError


def get_full_path(relative_path):
    return os.path.join(os.path.dirname(__file__), relative_path)


def gen_csv(interface, results, output):
    interface.print("Started generating CSV")
    output_name = regex.search(r"[^\/]+(?=\.csv$)", output).group(0)
    df = pd.DataFrame(results)
    df.to_csv(output_name + ".csv", index=False, sep="\t")
    interface.print("Finished generating " + output_name + ".csv")


def gen_model():
    writing_front_html = open(get_full_path("card_template/writing/front.html"), "r")
    writing_front = writing_front_html.read()
    writing_front_html.close()
    writing_back_html = open(get_full_path("card_template/writing/back.html"), "r")
    writing_back = writing_back_html.read()
    writing_back_html.close()

    reading_front_html = open(get_full_path("card_template/reading/front.html"), "r")
    reading_front = reading_front_html.read()
    reading_front_html.close()
    reading_traditional_front_html = open(
        get_full_path("card_template/reading/traditional_front.html"), "r"
    )
    reading_traditional_front = reading_traditional_front_html.read()
    reading_traditional_front_html.close()
    reading_back_html = open(get_full_path("card_template/reading/back.html"), "r")
    reading_back = reading_back_html.read()
    reading_back_html.close()
    reading_traditional_back_html = open(
        get_full_path("card_template/reading/traditional_back.html"), "r"
    )
    reading_traditional_back = reading_traditional_back_html.read()
    reading_traditional_back_html.close()

    styles_css = open(get_full_path("card_template/styles.css"), "r")
    styles = styles_css.read()
    styles_css.close()

    return genanki.Model(
        1354988330,
        "AnkiChinese",
        fields=[
            {"name": "Hanzi"},
            {"name": "Traditional"},
            {"name": "Definition"},
            {"name": "Pinyin"},
            {"name": "Pinyin 2"},
            {"name": "Examples"},
            {"name": "Formation"},
            {"name": "Frequency Rank"},
            {"name": "Frequency Count"},
            {"name": "HSK"},
            {"name": "Audio"},
        ],
        templates=[
            {
                "name": "AnkiChinese Writing",
                "qfmt": writing_front,
                "afmt": writing_back,
            },
            {
                "name": "AnkiChinese Simplified Reading",
                "qfmt": reading_front,
                "afmt": reading_back,
            },
            {
                "name": "AnkiChinese Traditional Reading",
                "qfmt": reading_traditional_front,
                "afmt": reading_traditional_back,
            }
        ],
        css=styles,
        sort_field_index=0,
    )


def gen_note(model, data):
    return genanki.Note(
        model=model,
        fields=[
            data["Hanzi"],
            data["Traditional"],
            data["Definition"],
            data["Pinyin"],
            data["Pinyin 2"],
            data["Examples"],
            data["Formation"],
            data["Frequency Rank"],
            data["Frequency Count"],
            data["HSK"],
            data["Audio"],
        ],
        guid=genanki.guid_for(data["Hanzi"]),
    )


def add_audio(package, audio_path):
    audio_files = os.listdir(audio_path)
    for file in audio_files:
        package.media_files.append(audio_path + "/" + file)


def gen_anki(interface, results, output):
    if interface:
        interface.print("Started generating AnkiChinese deck")
    output_path = os.path.abspath(output)
    output_name = os.path.splitext(os.path.basename(output_path))[0]
    deck = genanki.Deck(2085137232, output_name)
    model = gen_model()
    for data in results:
        deck.add_note(gen_note(model, data))

    package = genanki.Package(deck)
    add_audio(package, "ankichinese_audio")
    package.media_files.append(get_full_path("card_template/_CNstrokeorder.ttf"))
    package.write_to_file(output_path)
    if interface:
        interface.print("Finished generating " + output_name + ".apkg")


def update_anki(interface, results, anki, deck_name: str, model_name: str):
    interface.print(
        "Started updating\n\tdeck:\t\t" + deck_name + "\n\tmodel:\t\t" + model_name
    )

    notes = anki.notes(deck_name, model_name)
    model_fields = anki.model_fields(model_name)
    target_fields = (
        "Hanzi",
        "Traditional",
        "Definition",
        "Pinyin",
        "Pinyin 2",
        "Examples",
        "Formation",
        "HSK",
        "Frequency Rank",
        "Frequency Count",
        "Audio",
    )
    supported_fields = [field for field in model_fields if field in target_fields]
    if "Hanzi" not in model_fields:
        raise ValueError("Selected note type must contain a 'Hanzi' field.")

    notes_by_hanzi = {}
    for note in notes:
        value = note.get("fields", {}).get("Hanzi", {}).get("value", "")
        notes_by_hanzi.setdefault(value, []).append(note)

    updates = []
    additions = []
    for result in results:
        hanzi = result.get("Hanzi", "")
        fields = {name: str(result.get(name) or "") for name in supported_fields}
        if hanzi in notes_by_hanzi:
            for note in notes_by_hanzi[hanzi]:
                updated = {
                    name: value
                    for name, value in fields.items()
                    if note.get("fields", {}).get(name, {}).get("value", "") != value
                }
                if updated:
                    updates.append((note["noteId"], updated))
        else:
            additions.append({name: str(result.get(name) or "") for name in model_fields})

    media_names = set()
    for result in results:
        match = regex.search(r"\[sound:([^\]]+)\]", result.get("Audio", ""))
        if match:
            media_names.add(match.group(1))
    invalid_media_names = [
        name for name in media_names if os.path.basename(name) != name
    ]
    if invalid_media_names:
        interface.print(
            "Cannot update: invalid audio filename(s): {}".format(
                ", ".join(sorted(invalid_media_names))
            )
        )
        return
    missing_media = [
        name
        for name in sorted(media_names)
        if not os.path.isfile(os.path.join("ankichinese_audio", name))
    ]
    if missing_media:
        interface.print(
            "Cannot update: local audio file(s) are missing: {}. "
            "Run the scrape again to recreate them.".format(", ".join(missing_media))
        )
        return

    interface.print("\nUpdate summary for {} / {}:".format(deck_name, model_name))
    interface.print("Notes to update: {}".format(len(updates)))
    interface.print("Notes to add: {}".format(len(additions)))
    interface.print("Audio files to upload: {}".format(len(media_names)))
    if not interface.confirm("Apply these changes to Anki?"):
        interface.print("Update canceled")
        return

    package_path = None
    if additions:
        model_id = anki.model_ids().get(model_name)
        deck_id = anki.deck_ids().get(deck_name)
        templates = anki.model_templates(model_name)
        styling = anki.model_styling(model_name)
        if model_id is None or deck_id is None or not templates:
            raise AnkiConnectError(
                "Could not read the selected Anki deck and note type to "
                "prepare a safe package import."
            )

        package_templates = [
            {
                "name": name,
                "qfmt": template.get("Front", ""),
                "afmt": template.get("Back", ""),
            }
            for name, template in templates.items()
        ]
        is_cloze = any(
            "{{cloze:" in (template["qfmt"] + template["afmt"]).lower()
            for template in package_templates
        )
        model = genanki.Model(
            model_id,
            model_name,
            fields=[{"name": field} for field in model_fields],
            templates=package_templates,
            css=styling.get("css", ""),
            model_type=1 if is_cloze else 0,
        )

        deck = genanki.Deck(deck_id, deck_name)
        for fields in additions:
            deck.add_note(
                genanki.Note(
                    model=model,
                    fields=[str(fields.get(field) or "") for field in model_fields],
                    guid=genanki.guid_for(fields.get("Hanzi", "")),
                )
            )
        package = genanki.Package(deck)
        package_file = tempfile.NamedTemporaryFile(
            prefix="ankichinese_update_", suffix=".apkg", delete=False
        )
        package_path = package_file.name
        package_file.close()
        package.write_to_file(package_path)

    # Upload referenced sound files before changing note fields.
    applied = 0
    try:
        if media_names:
            interface.print("Uploading audio...")
        for media_name in sorted(media_names):
            media_path = os.path.join("ankichinese_audio", media_name)
            with open(media_path, "rb") as media_file:
                anki.invoke(
                    "storeMediaFile",
                    filename=media_name,
                    data=base64.b64encode(media_file.read()).decode("ascii"),
                )
            applied += 1

        interface.print("Applying note updates...")
        for note_id, fields in updates:
            anki.invoke("updateNoteFields", note={"id": note_id, "fields": fields})
            applied += 1
        if additions:
            imported = anki.invoke("importPackage", path=package_path)
            if imported is False:
                raise ValueError("AnkiConnect could not import the generated package.")
            imported_notes = anki.notes(deck_name, model_name)
            imported_by_hanzi = {
                note.get("fields", {}).get("Hanzi", {}).get("value", ""): note
                for note in imported_notes
            }
            missing_hanzi = [
                fields.get("Hanzi", "")
                for fields in additions
                if fields.get("Hanzi", "") not in imported_by_hanzi
                or not imported_by_hanzi[fields.get("Hanzi", "")].get("cards")
            ]
            if missing_hanzi:
                raise ValueError(
                    "Could not verify imported notes for: {}. Run Check "
                    "Database before retrying.".format(", ".join(missing_hanzi))
                )
            applied += len(additions)
    except (AnkiConnectError, OSError, ValueError) as exc:
        raise AnkiConnectError(
            "The update stopped after {} confirmed operation(s). Partial changes "
            "may be present; check Anki before retrying. {}".format(applied, exc)
        ) from exc
    finally:
        if package_path and os.path.exists(package_path):
            os.remove(package_path)

    interface.print(
        "Finished updating {} {} ({} updated, {} added).".format(
            deck_name, model_name, len(updates), len(additions)
        )
    )
