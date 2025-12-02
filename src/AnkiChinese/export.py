import genanki
import os
import pandas as pd
import re as regex


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
    reading_back_html = open(get_full_path("card_template/reading/back.html"), "r")
    reading_back = reading_back_html.read()
    reading_back_html.close()

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
                "name": "AnkiChinese Reading",
                "qfmt": reading_front,
                "afmt": reading_back,
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
            data["HSK"],
            data["Frequency Rank"],
            data["Frequency Count"],
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
    output_name = regex.search(r"[^\/]+(?=\.apkg$)", output).group(0)
    deck = genanki.Deck(2085137232, output_name)
    model = gen_model()
    for data in results:
        deck.add_note(gen_note(model, data))

    package = genanki.Package(deck)
    add_audio(package, "ankichinese_audio")
    package.media_files.append(get_full_path("card_template/_CNstrokeorder.ttf"))
    package.write_to_file(output_name + ".apkg")
    if interface:
        interface.print("Finished generating " + output_name + ".apkg")


def update_anki(interface, results, col, deck_name: str, model_name: str):
    interface.print(
        "Started updating\n\tdeck:\t\t" + deck_name + "\n\tmodel:\t\t" + model_name
    )

    # Get notes from deck and model
    cards = col.cards.merge_notes()
    cards_in_deck = cards[cards["cdeck"].str.startswith(deck_name)]
    notes_in_deck = col.notes[col.notes.nid.isin(cards_in_deck.nid)]
    selec = notes_in_deck.query(f"nmodel == '{model_name}'").copy()

    # Convert results to dataframe
    res = pd.DataFrame(results)
    res = res.add_prefix("nfld_")

    # Merge existing notes and results
    old = selec.fields_as_columns().copy()
    old.set_index("nfld_Hanzi", inplace=True)
    res.set_index("nfld_Hanzi", inplace=True)
    old.update(res)
    res.reset_index(inplace=True)
    old.reset_index(inplace=True)
    old = old.filter(regex="^nfld_", axis="columns")
    # Update exisiting notes
    selec["nflds"] = old.values.tolist()
    col.notes.update(selec)

    # Find and add new notes
    selec.fields_as_columns(inplace=True)
    new_notes = res[~res["nfld_Hanzi"].isin(selec["nfld_Hanzi"])]
    # Include only columns that also exist in existing notes
    diff_columns = old.columns.difference(new_notes.columns)
    new_notes.loc[:, diff_columns] = ""
    new_notes = new_notes[old.columns]
    new_notes.columns = new_notes.columns.str.replace("nfld_", "")
    col.notes.add_notes(
        nmodel=model_name, nflds=new_notes.to_dict("records"), inplace=True
    )

    # Print changes
    interface.print("Summary: ")
    summary = col.summarize_changes(output="dict")
    for key, value in summary.items():
        interface.print(str(key))
        for k, v in value.items():
            interface.print("\t" + str(k) + "\t\t" + str(v))

    notes_added_nids = col.notes.loc[col.notes.was_added()].nid.tolist()
    interface.print("\nNotes updated:")
    interface.print(col.notes.loc[col.notes.was_modified(), "nflds"].to_string())
    # interface.print("\nNotes added:")
    # interface.print(col.notes.loc[notes_added_nids, "nflds"].to_string())

    if interface.confirm("Apply changes?"):
        col.write(modify=True, add=True, delete=False)
        if len(notes_added_nids) > 0:
            col.cards.add_cards(notes_added_nids, deck_name, inplace=True)
            col.write(add=True)
        interface.print("Finished updating " + deck_name + " " + model_name)

        # Generate empty deck with audio files
        audio_data = []
        for audio_file in res.nfld_Audio.to_list():
            audio_data.append(
                {
                    "Hanzi": "",
                    "Traditional": "",
                    "Definition": "",
                    "Pinyin": "",
                    "Pinyin 2": "",
                    "Examples": "",
                    "Formation": "",
                    "HSK": "",
                    "Frequency Rank": "",
                    "Frequency Count": "",
                    "Audio": audio_file,
                }
            )
        gen_anki(
            None, audio_data, os.path.join(os.getcwd(), "ankichinese_audio.apkg")
        )
        interface.print(
            "Generated ankichinese_audio.apkg, import to Anki for deck audio"
        )
    else:
        interface.print("Update canceled")

    interface.print("\n\n\n")

    col.db.close()
