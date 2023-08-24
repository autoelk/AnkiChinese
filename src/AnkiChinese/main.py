import scraper
import export

import argparse


def cli():
    parser = argparse.ArgumentParser(
        description="Scrape ArchChinese for definitions and example words"
    )
    parser.add_argument(
        "--export",
        "-x",
        choices=["anki", "csv", "update"],
        default="anki",
        help="Export format (default: anki)\nanki: new Anki deck using AnkiChinese template\nupdate: update existing Anki deck\ncsv: CSV file",
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

    hanzi_list = []  # unfinished list of characters to scrape
    with open(args.input, encoding="utf8", errors="replace", mode="r") as f:
        for line in f:
            for hanzi in line:
                if not hanzi.isspace():
                    hanzi_list.append(hanzi)
    hanzi_list = set(hanzi_list)  # remove duplicates

    results = scraper.scrape(hanzi_list, args)
    print(f"Finished scraping {len(hanzi_list)} characters!")

    if args.export == "csv":
        export.gen_csv(results, args.output)
    elif args.export == "anki":
        export.gen_anki(results, args.output)
    elif args.export == "update":
        export.update_anki(results)


if __name__ == "__main__":
    cli()
