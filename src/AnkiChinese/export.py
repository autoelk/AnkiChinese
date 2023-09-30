import genanki
import os
import pandas as pd

from ankipandas import Collection


def gen_csv(results, output_name):
    df = pd.DataFrame(results)
    df.to_csv(output_name + ".csv", index=False, sep="\t")


def get_full_path(relative_path):
    return os.path.join(os.path.dirname(__file__), relative_path)


def gen_model():
    front_html = open(get_full_path("card_template/front.html"), "r")
    front = front_html.read()
    front_html.close()
    back_html = open(get_full_path("card_template/back.html"), "r")
    back = back_html.read()
    back_html.close()
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
            {"name": "HSK"},
            {"name": "Audio"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": front,
                "afmt": back,
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
            data["Audio"],
        ],
        guid=genanki.guid_for(data["Hanzi"]),
    )


def add_audio(package, audio_path):
    audio_files = os.listdir(audio_path)
    for file in audio_files:
        package.media_files.append(audio_path + "/" + file)


def gen_anki(results, output_name):
    deck = genanki.Deck(2085137232, output_name)
    model = gen_model()
    for data in results:
        deck.add_note(gen_note(model, data))

    package = genanki.Package(deck)
    add_audio(package, "ankichinese_audio")
    package.media_files.append(get_full_path("card_template/_CNstrokeorder.ttf"))
    package.write_to_file(output_name + ".apkg")


def update_anki(results, col, deck_name, model_name, notes_in_deck):
    selec = notes_in_deck.query(f"nmodel == '{model_name}'").copy()

    # convert results to dataframe
    res = pd.DataFrame(results)
    res = res.add_prefix("nfld_")

    # merge existing notes and results
    old = selec.fields_as_columns().copy()
    if "nfld_Hanzi" not in old.columns:
        print("Error: model must have 'Hanzi' column!")
        return
    old.set_index("nfld_Hanzi", inplace=True)
    res.set_index("nfld_Hanzi", inplace=True)
    old.update(res)
    res.reset_index(inplace=True)
    old.reset_index(inplace=True)
    old = old.filter(regex="^nfld_", axis="columns")
    # update exisiting notes
    selec["nflds"] = old.values.tolist()
    col.notes.update(selec)

    # find and add new notes
    selec.fields_as_columns(inplace=True)
    new_notes = res[~res["nfld_Hanzi"].isin(selec["nfld_Hanzi"])]
    # include only columns that also exist in existing notes
    diff_columns = old.columns.difference(new_notes.columns)
    new_notes.loc[:, diff_columns] = ""
    new_notes = new_notes[old.columns]
    new_notes.columns = new_notes.columns.str.replace("nfld_", "")
    col.notes.add_notes(
        nmodel=model_name, nflds=new_notes.to_dict("records"), inplace=True
    )

    # print changes and ask for confirmation
    # col.summarize_changes()
    notes_added_nids = col.notes.loc[col.notes.was_added()].nid.tolist()
    print("\nNotes updated:")
    print(col.notes.loc[col.notes.was_modified(), "nflds"])
    print("\nNotes added:")
    print(col.notes.loc[notes_added_nids, "nflds"])

    confirm_changes = input("Confirm changes? [y/n] ").lower().strip()
    if confirm_changes == "y" or confirm_changes == "yes":
        col.write(modify=True, add=True, delete=False)
        if len(notes_added_nids) > 0:
            col.cards.add_cards(notes_added_nids, deck_name, inplace=True)
            col.write(add=True)

    # generate empty deck with audio files
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
                "Audio": audio_file,
            }
        )
    gen_anki(audio_data, "ankichinese_audio")

    col.db.close()
