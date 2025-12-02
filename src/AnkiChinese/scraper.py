import asyncio
import aiometer
import functools
import re as regex
import requests
import os
import csv
from typing import Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Cached mapping from character -> (rank, count)
_CHAR_FREQ_MAP = None


def load_char_freq_map() -> dict:
    """Load the character frequency file into a dict.

    Returns a mapping of single-character string -> (int(rank), int(count)).
    """
    global _CHAR_FREQ_MAP
    if _CHAR_FREQ_MAP is not None:
        return _CHAR_FREQ_MAP

    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, "data")
    file_path = os.path.join(data_dir, "char_freq.tsv")

    if not os.path.exists(file_path):
        _CHAR_FREQ_MAP = {}
        return {}

    freq_map = {}
    with open(file_path, newline="", encoding="gb2312", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            # Skip header/comment lines
            if not row[0].strip().isdigit():
                continue

            rank = int(row[0].strip())
            char = row[1].strip()
            count = int(row[2].strip())
            freq_map[char] = (rank, count)

    _CHAR_FREQ_MAP = freq_map
    return _CHAR_FREQ_MAP


def clean_string(string) -> str:
    return regex.sub(" +", " ", string.strip().replace("\n", ""))


def scrape_basic_info(soup, num_examples) -> dict:
    char_def = soup.find("div", id="charDef").get_text().replace("\xa0", "").split("»")

    # Get information in first box
    details = dict()
    for detail in char_def:
        parts = detail.split(":")
        if len(parts) >= 2:
            details[parts[0].strip()] = clean_string(parts[1])

    pinyin_list = details.get("Pinyin", "").split(", ")
    info = {
        "Traditional": clean_string(details.get("Traditional Form", "")),
        "Definition": clean_string(
            ", ".join(details.get("Definition", "").split(", ")[:num_examples])
        ),
        "Pinyin": clean_string(pinyin_list[0]),
        "Pinyin 2": clean_string(", ".join(pinyin_list[1:])),
        "HSK": details.get("HSK Level", "None"),
        "Formation": details.get("Formation", ""),
    }
    return info


def scrape_example_words(soup, num_examples, num_defs) -> str:
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
                r'[\[].*?[\]]', "", ex_info[i + 1].select_one("p").get_text()
            ).split(", ")[:num_defs]
        )

        examples.append(word + "[" + ruby_text + "]: " + defn)

    return clean_string("<br>".join(examples))


def scrape_audio(soup) -> str:
    pinyin_tone = (
        regex.search(
            r'(?<=fn_playSinglePinyin\(")(.*)(?="\))',
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

    return f"[sound:{pinyin_tone}.mp3]"


def get_frequency(hanzi) -> tuple:
    """Load character frequency data and return the frequency of the given hanzi
    Args:
        hanzi (str): The Chinese character to look up.
    Returns:
        int: The frequency rank of the character
        int: The frequency count of the character
    """
    freq_map = load_char_freq_map()
    if not hanzi or hanzi not in freq_map:
        return None, None
    return freq_map[hanzi]


def scrape_word(r, num_examples, num_defs, hanzi) -> dict:
    soup = BeautifulSoup(r, "html5lib")

    info = dict()
    info["Hanzi"] = hanzi
    info.update(scrape_basic_info(soup, num_examples))
    info["Examples"] = scrape_example_words(soup, num_examples, num_defs)
    freq_rank, freq_count = get_frequency(hanzi)
    info["Frequency Rank"] = str(freq_rank) if freq_rank is not None else ""
    info["Frequency Count"] = str(freq_count) if freq_count is not None else ""
    info["Audio"] = scrape_audio(soup)

    return info


async def fetch(interface, context, num_examples, num_defs, hanzi) -> Optional[dict]:
    page = await context.new_page()
    await page.goto(
        f"https://www.archchinese.com/chinese_english_dictionary.html?find={hanzi}"
    )
    await page.wait_for_function("() => !!document.querySelector('#wordTable')")
    content = await page.content()
    await page.close()
    try:
        return scrape_word(content, num_examples, num_defs, hanzi)
    except Exception as e:
        interface.print(f"Error scraping {hanzi}: {e}")
        return None


async def main(
    chars,
    requests_at_once,
    requests_per_second,
    num_examples,
    num_defs,
    interface,
) -> list:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        interface.print("Started scraping")
        interface.start_pbar(len(chars))
        result_list = []
        async with aiometer.amap(
            functools.partial(fetch, interface, context, num_examples, num_defs),
            chars,
            max_at_once=requests_at_once,
            max_per_second=requests_per_second,
        ) as results:
            async for data in results:
                if data is not None:
                    result_list.append(data)
                await interface.step_pbar()
        await browser.close()
        interface.finish_pbar()
        interface.print(f"Finished scraping {len(chars)} character(s)")
        return result_list
