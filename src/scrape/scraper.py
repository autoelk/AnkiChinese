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
                    "qfmt": "<div>{{Audio}}</div>\n<h1 class='pinyin'>{{Pinyin}}</h1>\n<p class='pinyin2'>{{Pinyin 2}}</p>\n<p class='meaning'>{{Definition}}</p>\n",
                    "afmt": "<script>\n\tvar injectScript = (src) => {\n\t\treturn new Promise((resolve, reject) => {\n\t\t\tconst script = document.createElement('script');\n\t\t\tscript.src = src;\n\t\t\tscript.async = true;\n\t\t\tscript.onload = resolve;\n\t\t\tscript.onerror = reject;\n\t\t\tdocument.head.appendChild(script);\n\t\t});\n\t};\n\n\t(async () => {\n\t\tif (typeof HanziWriter === 'undefined') {\n\t\t\tawait injectScript('https://cdn.jsdelivr.net/npm/hanzi-writer@3.5/dist/hanzi-writer.min.js');\n\t\t}\n\n\t\tvar writer = HanziWriter.create('diagram', '{{Hanzi}}', {\n\t\t\twidth: 300,\n\t\t\theight: 300,\n\t\t\tradicalColor: '#337ab7',\n\t\t\tshowCharacter: false,\n\t\t\tshowOutline: true,\n\t\t\tdelayBetweenStrokes: 100,\n\t\t\tpadding: 5\n\t\t});\n\n\t\twriter.loopCharacterAnimation();\n\t})();\n</script>\n\n{{FrontSide}}\n\n<hr id=answer>\n<div class=notes style='color:gray'>HSK: {{HSK}}</div>\n<a id='diagram' href='plecoapi://x-callback-url/df?hw={{Hanzi}}'></a>\n\n<p>{{Words}}</p>\n<p>{{Formation}}</p>\n",
                }
            ],
            css=".card {\n font-family: arial;\n font-size: 20px;\n text-align: center;\n color: black;\n background-color: white;\n }\n",
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
        f"Finished reading input in {time.perf_counter() - start} seconds, starting scraping"
    )

    if args.type == "csv":
        results = asyncio.run(main_all(list_of_hanzi, args.numDefs, args.numExamples))

        df = pd.DataFrame(results)
        df.to_csv(args.output + ".csv", index=False)
    elif args.type == "anki":
        results = asyncio.run(main_itr(list_of_hanzi, args.numDefs, args.numExamples))

        genanki.Package(results).write_to_file(args.output + ".apkg")

    print(
        f"Finished scraping in {time.perf_counter() - start} seconds, wrote to {args.output} with file type {args.type}"
    )


if __name__ == "__main__":
    cli()
