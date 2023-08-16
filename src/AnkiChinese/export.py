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
    package.media_files.append("card_template/CNstrokeorder-0.0.4.7.ttf")
    package.write_to_file(args.output + ".apkg")

def update_anki(results, args):
    # get notes
    col = Collection()
    selec = col.notes.query("nmodel == 'Chinese'").copy()
    selec.fields_as_columns(inplace=True)

    res = pd.DataFrame(results)
    res = res.add_prefix("nfld_")

    # merge existing notes and results
    old = selec.filter(regex="^nfld_", axis='columns')
    old.set_index("nfld_Hanzi", inplace=True)
    res.set_index("nfld_Hanzi", inplace=True)
    print(old.columns)
    print(old.head(10))
    print(res.columns)
    print(res.head(10))
    old.update(res)
    print(old.head(10))

    selec.fields_as_list(inplace=True)
    selec["nfld"] = old

    # find new notes
    # new_notes = res[~res.index.isin(selec.index)]
    # common_columns = selec.columns.intersection(new_notes.columns)
    # new_notes = new_notes[common_columns]
    # new_notes.reset_index(inplace=True)
    # new_notes.columns = new_notes.columns.str.replace("nfld_", "")
    # col.notes.add_notes(nmodel="Chinese", nflds=new_notes.to_dict('records'), inplace=True)

    # selec.reset_index(inplace=True)

    col.notes.update(selec)

    col.summarize_changes()
    # col.write(modify=True, add=True, delete=False)
    col.db.close()