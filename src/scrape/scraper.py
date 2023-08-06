import asyncio
import aiometer
import functools

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

import pandas as pd
import re as regex
import time
import argparse

import genanki


class MyNote(genanki.Note):
    @property
    def guid(self):
        return genanki.guid_for(self.fields[0])


def cleanStr(string):
    return regex.sub(" +", " ", string.strip().replace("\n", ""))


def scrapeWord(r, numDefs, numExamples, hanzi):
    soup = BeautifulSoup(r, "html5lib")

    # Get basic info
    charDef = soup.find("div", id="charDef").get_text().replace("\xa0", "").split("»")

    # Get all information on page
    details = dict()
    for detail in charDef:
        x = detail.split(":")
        if len(x) >= 2:
            details[x[0].strip()] = cleanStr(x[1])

    pinyinLst = details["Pinyin"].split(", ")
    info = {
        "hanzi": hanzi,
        "definition": cleanStr(", ".join(details["Definition"].split(", ")[:numDefs])),
        "pinyin": cleanStr(pinyinLst[0]),
        "pinyin2": cleanStr(", ".join(pinyinLst[1:])) if len(pinyinLst) > 1 else "",
        "hsk": details["HSK Level"] if "HSK Level" in details else "",
        "formation": details["Formation"] if "Formation" in details else "",
    }

    # Get examples
    wordTable = soup.select_one("#wordPaneContent #wordTable")

    exWords = wordTable.select(".word-container .char-effect:first-child")
    exInfo = wordTable.select(".col-md-7")

    examples = []
    for i in range(min(numExamples, len(exWords))):
        word = exWords[i].text
        pinyin = exInfo[i + 1].select_one("p>a").get_text()
        defn = ", ".join(
            regex.sub(
                "[\[].*?[\]]", "", exInfo[i + 1].select_one("p").get_text()
            ).split(", ")[:numDefs]
        )

        examples.append(word + "[" + pinyin + "]: " + defn)

    info["examples"] = cleanStr("<br>".join(examples))

    return info


async def fetch(context, numDefs, numExamples, hanzi):
    page = await context.new_page()
    await page.goto(
        f"https://www.archchinese.com/chinese_english_dictionary.html?find={hanzi}"
    )
    await page.wait_for_function("() => !!document.querySelector('#wordTable')")
    content = await page.content()
    await page.close()
    return scrapeWord(content, numDefs, numExamples, hanzi)


async def main_all(chars, numDefs, numExamples):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        tasks = [
            functools.partial(fetch, context, numDefs, numExamples, hanzi)
            for hanzi in chars
        ]
        results = await aiometer.run_all(tasks, max_at_once=10, max_per_second=5)
        await browser.close()
        return results


async def main_itr(chars, numDefs, numExamples):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        front_html = open("card_template/front.html", "r")
        front = front_html.read()
        front_html.close()
        back_html = open("card_template/back.html", "r")
        back = back_html.read()
        back_html.close()
        styles_css = open("card_template/styles.css", "r")
        styles = styles_css.read()
        styles_css.close()

        chinese_model = genanki.Model(
            1607392319,
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
        )

        deck = genanki.Deck(2059400110, "AnkiChinese Deck")

        async with aiometer.amap(
            functools.partial(fetch, context, numDefs, numExamples),
            chars,
            max_at_once=10,
            max_per_second=5,
        ) as results:
            async for data in results:
                note = genanki.Note(
                    model=chinese_model,
                    fields=[
                        data["hanzi"],
                        data["definition"],
                        data["pinyin"],
                        data["pinyin2"],
                        data["examples"],
                        data["formation"],
                        data["hsk"],
                        "",
                    ],
                )
                deck.add_note(note)
        await browser.close()
        return deck


def cli():
    parser = argparse.ArgumentParser(
        description="Scrape ArchChinese for definitions and example words"
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
        "--type",
        "-t",
        type=str,
        choices=["anki", "csv"],
        default="anki",
        help="Output file type (default: anki)",
    )
    parser.add_argument(
        "--numDefs",
        "-d",
        type=int,
        default=5,
        help="Number of definitions to scrape per character (default: 5)",
    )
    parser.add_argument(
        "--numExamples",
        "-e",
        type=int,
        default=3,
        help="Number of example words to scrape per character (default: 3)",
    )

    args = parser.parse_args()

    start = time.perf_counter()
    list_of_hanzi = []  # unfinished list of characters to scrape
    with open(args.input, encoding="utf8", errors="replace", mode="r") as f:
        for line in f:
            for hanzi in line:
                if not hanzi.isspace():
                    list_of_hanzi.append(hanzi)
    print(
        f"Finished reading input in {round(time.perf_counter() - start, 4)} seconds, starting scraping"
    )

    if args.type == "csv":
        results = asyncio.run(main_all(list_of_hanzi, args.numDefs, args.numExamples))

        df = pd.DataFrame(results)
        df.to_csv(args.output + ".csv", index=False)
    elif args.type == "anki":
        results = asyncio.run(main_itr(list_of_hanzi, args.numDefs, args.numExamples))

        package = genanki.Package(results)
        package.media_files = ["card_template/CNstrokeorder-0.0.4.7.ttf"]
        package.write_to_file(args.output + ".apkg")

    print(
        f"Finished scraping in {round(time.perf_counter() - start, 4)} seconds, wrote to {args.output} with file type {args.type}"
    )


if __name__ == "__main__":
    cli()
