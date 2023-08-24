import genanki
import os
import pandas as pd

from ankipandas import Collection


def gen_csv(results, output_name):
    df = pd.DataFrame(results)
    df.to_csv(output_name + ".csv", index=False, sep="\t")


def gen_model():
    front_html = open("card_template/front.html", "r")
    front = front_html.read()
    front_html.close()
    back_html = open("card_template/back.html", "r")
    back = back_html.read()
    back_html.close()
    styles_css = open("card_template/styles.css", "r")
    styles = styles_css.read()
    styles_css.close()

    return genanki.Model(
        1354988330,
        "AnkiChinese",
        fields=[
            {"name": "Hanzi"},
            {"name": "Definition"},
            {"name": "Pinyin"},
            {"name": "Pinyin 2"},
            {"name": "Words"},
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


def gen_anki(results, output_name):
    deck = genanki.Deck(2085137232, "AnkiChinese Deck")
    model = gen_model()
    for data in results:
        deck.add_note(gen_note(model, data))

    package = genanki.Package(deck)
    audio_files = os.listdir("ankichinese_audio")
    for file in audio_files:
        package.media_files.append("ankichinese_audio/" + file)
    package.media_files.append("card_template/_CNstrokeorder.ttf")
    package.write_to_file(output_name + ".apkg")


def update_anki(results):
    # get desired notes
    col = Collection()

    deck_names = col.cards.list_decks()
    deck_name = ""
    if len(deck_names) == 0:
        print("No decks found!")
        return
    elif len(deck_names) == 1:
        deck_name = deck_names[0]
        print("Deck: " + deck_name)
    else:
        print("Decks: " + ", ".join(deck_names))
        while deck_name not in deck_names:
            deck_name = input("Enter name of deck to update: ")

    cards_in_deck = col.cards.merge_notes()
    cards_in_deck = cards_in_deck[cards_in_deck["cdeck"].str.startswith(deck_name)]
    notes_in_deck = col.notes[col.notes.nid.isin(cards_in_deck.nid)]

    model_names = notes_in_deck.list_models()
    model_name = ""
    if len(model_names) == 0:
        print("No models found!")
        return
    elif len(model_names) == 1:
        model_name = model_names[0]
        print("Model: " + model_name)
    else:
        print("Models: " + ", ".join(model_names))
        while model_name not in model_names:
            model_name = input("Enter name of model to update: ")

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
    print(col.notes.loc[col.notes.was_modified()])
    print("\nNotes added:")
    print(col.notes.loc[notes_added_nids])

    confirm = input("Confirm changes? [y/n] ").lower().strip()
    if confirm == "y" or confirm == "yes":
        col.write(modify=True, add=True, delete=False)
        col.cards.add_cards(notes_added_nids, deck_name, inplace=True)
        col.write(add=True)

    col.db.close()
