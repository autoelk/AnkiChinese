import genanki
import os
import pandas as pd

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
        "Chinese Model",
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

def gen_anki(results, args):
    note_model = gen_model()
    deck = genanki.Deck(2085137232, "AnkiChinese Deck")
    for data in results:
        note = genanki.Note(
            model=note_model,
            fields=[
                data["hanzi"],
                data["definition"],
                data["pinyin"],
                data["pinyin2"],
                data["examples"],
                data["formation"],
                data["hsk"],
                data["audio"],
            ],
            guid=genanki.guid_for(data["hanzi"]),
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    audio_files = os.listdir("ankichinese_audio")
    for file in audio_files:
        package.media_files.append("ankichinese_audio/" + file)
    package.media_files.append("card_template/CNstrokeorder-0.0.4.7.ttf")
    package.write_to_file(args.output + ".apkg")