import sys
import os.path

sys.path.insert(1, os.path.dirname(__file__))  # allows python to find other modules

import scraper
import export

import argparse

from ankipandas import Collection


def cli():
    parser = argparse.ArgumentParser(
        description="Scrape ArchChinese for definitions and example words"
    )
    parser.add_argument(
        "--export",
        "-x",
        choices=["anki", "csv", "update"],
        default="anki",
        help="""Export mode (default: anki) 
        ANKI: Generate new AnkiChinese deck 
        CSV: Generate CSV file 
        UPDATE: Update existing deck""",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="input.txt",
        help="Input file with characters to scrape (default: input.txt)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="ankchinese_output",
        help="Name of output file (do not include extension) (default: ankichinese_output)",
    )
    parser.add_argument(
        "--definitions",
        "-def",
        type=int,
        default=5,
        help="Number of definitions to scrape per character (default: 5)",
    )
    parser.add_argument(
        "--examples",
        "-ex",
        type=int,
        default=5,
        help="Number of example words to scrape per character (default: 5)",
    )
    parser.add_argument(
        "--requests-at-once",
        "-r",
        type=int,
        default=10,
        help="Maximum number of requests at once (default: 10)",
    )
    parser.add_argument(
        "--requests-per-second",
        "-rs",
        type=int,
        default=5,
        help="Maximum number of requests per second (default: 5)",
    )
    args = parser.parse_args()
    print(args)

    chars = []  # list of characters to scrape
    try:
        with open(args.input, encoding="utf8", errors="replace", mode="r") as f:
            for line in f:
                for char in line:
                    if not char.isspace():
                        chars.append(char)
    except FileNotFoundError as e:
        print(e)

    chars = set(chars)  # remove duplicates
    if len(chars) == 0:
        print("No characters found!")
        return

    export_mode = args.export
    if export_mode == "csv":
        results = scraper.scrape(
            chars,
            args.requests_at_once,
            args.requests_per_second,
            args.examples,
            args.definitions,
        )
        export.gen_csv(results, os.path.join(os.getcwd(), args.output + ".csv"))
    elif export_mode == "anki":
        results = scraper.scrape(
            chars,
            args.requests_at_once,
            args.requests_per_second,
            args.examples,
            args.definitions,
        )
        export.gen_anki(results, os.path.join(os.getcwd(), args.output + ".apkg"))
    elif export_mode == "update":
        col = Collection()

        # get desired notes
        deck_names = col.cards.list_decks()
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

        fields = (
            notes_in_deck.fields_as_columns()
            .filter(regex="^nfld_", axis="columns")
            .columns.str.replace("nfld_", "")
        )

        scraped_fields = [
            "Hanzi",
            "Traditional",
            "Definition",
            "Pinyin",
            "Pinyin 2",
            "Examples",
            "Formation",
            "HSK",
            "Audio",
        ]

        print("\nAnkiChinese will update the following fields in your model:")
        for field in fields:
            if field in scraped_fields:
                print(">> " + field)
            else:
                print("-- " + field)
        print("")

        if "Hanzi" not in fields:
            raise Exception("Error: model must have 'Hanzi' field!")

        use_model = input("Use this model? [y/n] ").lower().strip()
        if use_model != "y" and use_model != "yes":
            print("Quitting ...")
            return

        existing_chars = []
        use_db = input("Also update characters in deck? [y/n] ").lower().strip()
        if use_db == "y" or use_db == "yes":
            existing_chars = notes_in_deck.fields_as_columns().nfld_Hanzi.to_list()

        chars.update(existing_chars)
        results = scraper.scrape(
            chars,
            args.requests_at_once,
            args.requests_per_second,
            args.examples,
            args.definitions,
        )
        export.update_anki(results, col, deck_name, model_name, notes_in_deck)


if __name__ == "__main__":
    cli()
