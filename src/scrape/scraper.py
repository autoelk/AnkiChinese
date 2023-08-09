import asyncio
import aiometer
import functools

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

import pandas as pd
import re as regex
import argparse
from tqdm import tqdm

import genanki
import requests
import os


def clean_string(string):
    return regex.sub(" +", " ", string.strip().replace("\n", ""))


def scrape_word(r, num_defs, num_examples, hanzi):
    soup = BeautifulSoup(r, "html5lib")

    # Get basic info
    char_def = soup.find("div", id="charDef").get_text().replace("\xa0", "").split("»")

    # Get all information on page
    details = dict()
    for detail in char_def:
        parts = detail.split(":")
        if len(parts) >= 2:
            details[parts[0].strip()] = clean_string(parts[1])

    pinyin_list = details.get("Pinyin", "").split(", ")
    info = {
        "hanzi": hanzi,
        "definition": clean_string(
            ", ".join(details.get("Definition", "").split(", ")[:num_defs])
        ),
        "pinyin": clean_string(pinyin_list[0]),
        "pinyin2": clean_string(", ".join(pinyin_list[1:])),
        "hsk": details.get("HSK Level", "None"),
        "formation": details.get("Formation", ""),
    }

    # Get examples
    word_table = soup.select_one("#wordPaneContent #wordTable")

    ex_words = word_table.select(".word-container .char-effect:first-child")
    ex_info = word_table.select(".col-md-7")

    examples = []
    for i in range(min(num_examples, len(ex_words))):
        word = ex_words[i].text
        ruby_list = []  # Pinyin to appear above word
        for part in ex_info[i + 1].select("p>a>span"):
            ruby_list.append(part.get_text())
        ruby_text = " ".join(ruby_list)
        defn = ", ".join(
            regex.sub(
                "[\[].*?[\]]", "", ex_info[i + 1].select_one("p").get_text()
            ).split(", ")[:num_defs]
        )

        examples.append(word + "[" + ruby_text + "]: " + defn)

    info["examples"] = clean_string("<br>".join(examples))

    # Get audio
    pinyin_tone = (
        regex.search(
            '(?<=fn_playSinglePinyin\(")(.*)(?="\))',
            soup.select_one("#primaryPinyin a.arch-pinyin-font").get("onclick"),
        )
        .group(0)
        .lower()
    )

    file_path = f"ankichinese_audio/{pinyin_tone}.mp3"
    if not os.path.exists(file_path):
        r = requests.get(f"https://cdn.yoyochinese.com/audio/pychart/{pinyin_tone}.mp3")
        if r.status_code == 404:
            r = requests.get(f"https://www.purpleculture.net/mp3/{pinyin_tone}.mp3")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(r.content)

    info["audio"] = f"[sound:{pinyin_tone}.mp3]"

    return info


async def fetch(context, num_defs, num_examples, hanzi):
    page = await context.new_page()
    await page.goto(
        f"https://www.archchinese.com/chinese_english_dictionary.html?find={hanzi}"
    )
    await page.wait_for_function("() => !!document.querySelector('#wordTable')")
    content = await page.content()
    await page.close()
    try:
        return scrape_word(content, num_defs, num_examples, hanzi)
    except Exception as e:
        print(f"Error scraping {hanzi}: {e}")
        return None


async def main_csv(chars, num_defs, num_examples):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        pbar = tqdm(total=len(chars))
        result_list = []
        async with aiometer.amap(
            functools.partial(fetch, context, num_defs, num_examples),
            chars,
            max_at_once=10,
            max_per_second=5,
        ) as results:
            async for data in results:
                if data is None:
                    continue
                result_list.append(data)
                pbar.update(1)
        await browser.close()
        pbar.close()
        return result_list


async def main_anki(chars, num_defs, num_examples):
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
            sort_field_index=0,
        )

        deck = genanki.Deck(2059400110, "AnkiChinese Deck")

        pbar = tqdm(total=len(chars))
        async with aiometer.amap(
            functools.partial(fetch, context, num_defs, num_examples),
            chars,
            max_at_once=10,
            max_per_second=5,
        ) as results:
            async for data in results:
                if data is None:
                    continue
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
                        data["audio"],
                    ],
                    guid=genanki.guid_for(data["hanzi"]),
                )
                deck.add_note(note)
                pbar.update(1)
        await browser.close()
        pbar.close()
        return deck


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

    if args.csv:
        results = asyncio.run(main_csv(hanzi_list, args.defs, args.examples))

        df = pd.DataFrame(results)
        df.to_csv(args.output + ".csv", index=False)
    else:
        results = asyncio.run(main_anki(hanzi_list, args.defs, args.examples))

        package = genanki.Package(results)
        audio_files = os.listdir("ankichinese_audio")
        print(f"Adding {len(audio_files)} audio files.")
        for file in tqdm(audio_files):
            package.media_files.append("ankichinese_audio/" + file)
        package.media_files.append("card_template/CNstrokeorder-0.0.4.7.ttf")
        package.write_to_file(args.output + ".apkg")

    print(f"Finished scraping {len(hanzi_list)} characters!")


if __name__ == "__main__":
    cli()
