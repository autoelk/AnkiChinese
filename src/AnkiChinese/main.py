import sys
import os.path

sys.path.insert(1, os.path.dirname(__file__))
import scraper
import export

from ankipandas import Collection
from gooey import Gooey, GooeyParser


def add_advanced_args(parser):
    advanced_args = parser.add_argument_group("Advanced")
    advanced_args.add_argument(
        "--definitions",
        "-def",
        type=int,
        default=5,
        help="Number of definitions to scrape per character (default: 5)",
        widget="IntegerField",
    )
    advanced_args.add_argument(
        "--examples",
        "-ex",
        type=int,
        default=5,
        help="Number of example words to scrape per character (default: 5)",
        widget="IntegerField",
    )
    advanced_args.add_argument(
        "--requests-at-once",
        "-r",
        type=int,
        default=10,
        help="Maximum number of requests at once (default: 10)",
        widget="IntegerField",
    )
    advanced_args.add_argument(
        "--requests-per-second",
        "-rs",
        type=int,
        default=5,
        help="Maximum number of requests per second (default: 5)",
        widget="IntegerField",
    )
    return advanced_args


def get_model(col, deck_name):
    cards_in_deck = col.cards.merge_notes()
    cards_in_deck = cards_in_deck[cards_in_deck["cdeck"].str.startswith(deck_name)]
    notes_in_deck = col.notes[col.notes.nid.isin(cards_in_deck.nid)]

    model_names = notes_in_deck.list_models()
    if len(model_names) == 0:
        raise TypeError("Deck contains no models")
    elif len(model_names) == 1:
        model_name = model_names[0]
    else:
        raise TypeError("Deck contains multiple models")

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
        raise TypeError("Model must have 'Hanzi' field!")

    return model_name, notes_in_deck


@Gooey(
    program_name="AnkiChinese",
    navigation="TABBED",
    progress_regex=r"^(?P<current>\d+) / (?P<total>\d+)$",
    progress_expr="current / total * 100",
    hide_progress_msg=True,
)
def main():
    parser = GooeyParser(description="Generate Anki flashcards")

    subs = parser.add_subparsers(help="Export Methods", dest="export")

    # AnkiChinese Deck
    deck_output_parser = subs.add_parser("Deck", help="Generate a new Anki deck")
    deck_output_parser.add_argument(
        "Input",
        help="Input file with characters to scrape (.txt)",
        default="./input.txt",
        widget="FileChooser",
    )
    deck_output_parser.add_argument(
        "Output",
        help="Name of output file (.apkg)",
        default="ankichinese_output",
        widget="TextField",
    )

    # CSV
    csv_output_parser = subs.add_parser("CSV", help="Generate a CSV file")
    csv_output_parser.add_argument(
        "Input",
        help="Input file with characters to scrape (.txt)",
        default="./input.txt",
        widget="FileChooser",
    )
    csv_output_parser.add_argument(
        "Output",
        help="Name of output file (.csv)",
        default="ankichinese_output",
        widget="TextField",
    )

    # Update Existing Deck
    col = Collection()
    deck_names = col.cards.list_decks()

    update_output_parser = subs.add_parser("Update", help="Update existing Anki deck")
    update_output_parser.add_argument(
        "Input",
        help="Input file with characters to scrape (.txt)",
        default="./input.txt",
        widget="FileChooser",
    )
    update_output_parser.add_argument(
        "Deck",
        default=deck_names[0],
        choices=deck_names,
        widget="FilterableDropdown",
    )
    update_output_parser.add_argument(
        "Confirm",
        help=" I have backed up my deck and am ready to modify it",
        widget="CheckBox",
    )

    add_advanced_args(csv_output_parser)
    add_advanced_args(deck_output_parser)
    update_advanced_args = add_advanced_args(update_output_parser)
    update_advanced_args.add_argument(
        "--Update",
        help=" Also update characters already in deck",
        widget="CheckBox",
    )

    args = parser.parse_args()

    if args.export != "Update":
        col.db.close()

    hanzi_list = []  # list of characters to scrape
    try:
        with open(args.Input, encoding="utf8", errors="replace", mode="r") as f:
            for line in f:
                for hanzi in line:
                    if not hanzi.isspace():
                        hanzi_list.append(hanzi)
    except FileNotFoundError as e:
        print(e)

    hanzi_list = set(hanzi_list)  # remove duplicates
    if len(hanzi_list) == 0:
        print("No characters found!")
        return
    results = scraper.scrape(hanzi_list, args)
    print(f"Finished scraping {len(hanzi_list)} characters!")

    if args.export == "CSV":
        export.gen_csv(results, args.Output)
    elif args.export == "Deck":
        export.gen_anki(results, args.Output)
    elif args.export == "Update":
        if not args.Confirm:
            return
        model_name, notes_in_deck = get_model(col, args.Deck)
        if args.Update:
            hanzi_list.extend(notes_in_deck.fields_as_columns().nfld_Hanzi.to_list())
        export.update_anki(results, col, args.Deck, model_name, notes_in_deck)


if __name__ == "__main__":
    main()
