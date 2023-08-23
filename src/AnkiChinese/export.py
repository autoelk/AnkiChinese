import genanki
import os
import pandas as pd

from ankipandas import Collection


def gen_csv(results, args):
    df = pd.DataFrame(results)
    df.to_csv(args.output + ".csv", index=False, sep="\t")


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


def gen_anki(results, args):
    deck = genanki.Deck(2085137232, "AnkiChinese Deck")
    model = gen_model()
    for data in results:
        deck.add_note(gen_note(model, data))

    package = genanki.Package(deck)
    audio_files = os.listdir("ankichinese_audio")
    for file in audio_files:
        package.media_files.append("ankichinese_audio/" + file)
    package.media_files.append("card_template/_CNstrokeorder.ttf")
    package.write_to_file(args.output + ".apkg")


def update_anki(results, args):
    DECK_NAME = "Cornell CHIN"
    MODEL_NAME = "Chinese"

    # get notes
    col = Collection()
    selec = col.notes.query(f"nmodel == '{MODEL_NAME}'").copy()
    selec.fields_as_columns(inplace=True)

    res = pd.DataFrame(results)
    res = res.add_prefix("nfld_")

    # merge existing notes and results
    old = selec.copy()
    old.set_index("nfld_Hanzi", inplace=True)
    res.set_index("nfld_Hanzi", inplace=True)
    old.update(res)
    res.reset_index(inplace=True)
    old.reset_index(inplace=True)
    old = old.filter(regex="^nfld_", axis="columns")
    # update exisiting notes
    selec.fields_as_list(inplace=True)
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
        nmodel=MODEL_NAME, nflds=new_notes.to_dict("records"), inplace=True
    )

    # print changes and ask for confirmation
    col.summarize_changes()
    notes_added_nids = col.notes.loc[col.notes.was_added()].nid.tolist()
    print(col.notes.loc[notes_added_nids])

    confirm = input("Confirm changes? [y/n] ").lower().strip()
    if confirm == "y" or confirm == "yes":
        col.write(modify=True, add=True, delete=False)
        col.cards.add_cards(notes_added_nids, DECK_NAME, inplace=True)
        col.write(add=True)

    col.db.close()
