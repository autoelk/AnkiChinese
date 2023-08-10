import argparse
import scraper


def cli():
    parser = argparse.ArgumentParser(
        description="Scrape ArchChinese for definitions and example words"
    )
    parser.add_argument(
        "-csv",
        default=False,
        action="store_true",
        help="Output to CSV instead of Anki deck",
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
        "--defs",
        "-d",
        type=int,
        default=5,
        help="Number of definitions to scrape per character (default: 5)",
    )
    parser.add_argument(
        "--examples",
        "-e",
        type=int,
        default=3,
        help="Number of example words to scrape per character (default: 3)",
    )
    args = parser.parse_args()

    hanzi_list = []  # unfinished list of characters to scrape
    with open(args.input, encoding="utf8", errors="replace", mode="r") as f:
        for line in f:
            for hanzi in line:
                if not hanzi.isspace():
                    hanzi_list.append(hanzi)
    hanzi_list = set(hanzi_list)  # remove duplicates

    scraper.scrape(hanzi_list, args)


if __name__ == "__main__":
    cli()
