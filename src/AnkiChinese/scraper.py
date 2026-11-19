import asyncio
import aiometer
import functools
import re as regex
import requests
import os
import csv
import unicodedata
from typing import Optional
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .frequency import load_char_freq_map, word_frequency

_HSK_LEVEL_MAP = None

# Return the dictionary fragments as soon as the scraper's data is available.
DICTIONARY_HTML = """
() => {
    const definition = document.querySelector('div#charDef');
    const words = document.querySelector('#wordPaneContent #wordTable');
    const pronunciation = document.querySelector('#primaryPinyin a.arch-pinyin-font[onclick]');
    if (!definition || !words || !pronunciation) return false;
    return definition.outerHTML
        + '<div id="wordPaneContent">' + words.outerHTML + '</div>'
        + '<div id="primaryPinyin">' + pronunciation.outerHTML + '</div>';
}
"""


def load_hsk_level_map() -> dict:
    """Load the official HSK 3.0 character recognition levels.

    Returns a mapping from a single Chinese character to its syllabus level.
    """
    global _HSK_LEVEL_MAP
    if _HSK_LEVEL_MAP is not None:
        return _HSK_LEVEL_MAP

    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(base_dir, "data", "HSK-3.0-characters.csv")
    if not os.path.exists(file_path):
        _HSK_LEVEL_MAP = {}
        return _HSK_LEVEL_MAP

    hsk_map = {}
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            char = (row.get("Character") or "").strip()
            level = (row.get("Level") or "").strip()
            if len(char) == 1 and level in {"1", "2", "3", "4", "5", "6", "7-9"}:
                hsk_map[char] = level

    _HSK_LEVEL_MAP = hsk_map
    return _HSK_LEVEL_MAP


def get_hsk_level(hanzi) -> str:
    """Return the HSK 3.0 recognition-list level for a character, if listed."""
    return load_hsk_level_map().get(hanzi, "")


def unique_hanzi(text: str) -> set:
    return {
        char
        for char in text
        if unicodedata.name(char, "").startswith(
            ("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-")
        )
    }


def clean_string(string) -> str:
    return regex.sub(" +", " ", string.strip().replace("\n", ""))


def scrape_basic_info(soup, num_defs) -> dict:
    char_def = soup.find("div", id="charDef").get_text().replace("\xa0", "").split("»")

    # Get information in first box
    details = dict()
    for detail in char_def:
        parts = detail.split(":")
        if len(parts) >= 2:
            details[parts[0].strip()] = clean_string(parts[1])

    info = {
        "Traditional": clean_string(details.get("Traditional Form", "")),
        "Definition": clean_string(
            ", ".join(details.get("Definition", "").split(", ")[:num_defs])
        ),
        "Pinyin": details.get("Pinyin", ""),
        "Formation": details.get("Formation", ""),
    }
    return info


def scrape_example_words(soup, num_examples, num_defs) -> str:
    word_table = soup.select_one("#wordPaneContent #wordTable")

    entries = []
    for row in word_table.select("tr"):
        word = row.select_one("td.col-md-3 > a.char-effect:first-child")
        details = row.select_one(".col-md-7 p")
        if word is None or details is None:
            continue
        entries.append((word.get_text(strip=True), details))

    entries.sort(key=lambda entry: -word_frequency(entry[0]))
    examples = []
    for word, details in entries[:max(0, num_examples)]:
        ruby_list = []  # Pinyin to appear above word
        for part in details.select(":scope > a > span"):
            ruby_list.append(part.get_text())
        ruby_text = " ".join(ruby_list)
        defn = ", ".join(
            regex.sub(
                r'[\[].*?[\]]', "", details.get_text()
            ).split(", ")[:num_defs]
        )

        examples.append(word + "[" + ruby_text + "]: " + defn)

    return clean_string("<br>".join(examples))


def audio_filename(soup) -> str:
    pinyin_tone = (
        regex.search(
            r'(?<=fn_playSinglePinyin\(")(.*)(?="\))',
            soup.select_one("#primaryPinyin a.arch-pinyin-font").get("onclick"),
        )
        .group(0)
        .lower()
    )

    return f"{pinyin_tone}.mp3"


def download_audio(file_path):
    filename = os.path.basename(file_path)
    response = requests.get(
        f"https://cdn.yoyochinese.com/audio/pychart/{filename}", timeout=15
    )
    if response.status_code == 404:
        response = requests.get(
            f"https://www.purpleculture.net/mp3/{filename}", timeout=15
        )
    response.raise_for_status()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as stream:
        stream.write(response.content)


def get_frequency(hanzi) -> tuple:
    """Load character frequency data and return the frequency of the given hanzi
    Args:
        hanzi (str): The Chinese character to look up.
    Returns:
        int: The frequency rank of the character
        float: Blended occurrences per million characters
    """
    freq_map = load_char_freq_map()
    if not hanzi or hanzi not in freq_map:
        return None, None
    return freq_map[hanzi]


def scrape_word(r, num_examples, num_defs, hanzi) -> tuple:
    soup = BeautifulSoup(r, "html.parser")

    info = dict()
    info["Hanzi"] = hanzi
    info.update(scrape_basic_info(soup, num_defs))
    info["HSK"] = get_hsk_level(hanzi)
    info["Examples"] = scrape_example_words(soup, num_examples, num_defs)
    freq_rank, freq_per_million = get_frequency(hanzi)
    info["Frequency Rank"] = str(freq_rank) if freq_rank is not None else ""
    info["Frequency Score"] = (
        "{:.2f}".format(freq_per_million) if freq_per_million is not None else ""
    )
    filename = audio_filename(soup)
    info["Audio"] = f"[sound:{filename}]"
    return info, filename


async def fetch(
    interface, context, num_examples, num_defs, audio_locks, hanzi
) -> Optional[dict]:
    url = f"https://www.archchinese.com/chinese_english_dictionary.html?find={hanzi}"
    for attempt in range(2):
        try:
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded")
                fragments = await page.wait_for_function(DICTIONARY_HTML)
                content = await fragments.json_value()
            finally:
                await page.close()
        except PlaywrightTimeoutError as exc:
            if attempt == 0:
                interface.print(f"Timed out loading {hanzi}. Retrying once.")
                await asyncio.sleep(1)
                continue
            detail = str(exc).partition("\n")[0]
            interface.print(f"Skipping {hanzi} after two attempts: {detail}")
            return None
        except PlaywrightError as exc:
            detail = str(exc).partition("\n")[0]
            interface.print(f"Skipping {hanzi}: {detail}")
            return None
        break

    try:
        info, filename = scrape_word(content, num_examples, num_defs, hanzi)
        file_path = os.path.join("ankichinese_audio", filename)
        async with audio_locks.setdefault(filename, asyncio.Lock()):
            if not os.path.exists(file_path):
                await asyncio.get_running_loop().run_in_executor(
                    None, download_audio, file_path
                )
        return info
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
    chars = unique_hanzi(chars)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        interface.print("Started scraping")
        interface.start_pbar(len(chars))
        result_list = []
        audio_locks = {}
        async with aiometer.amap(
            functools.partial(
                fetch, interface, context, num_examples, num_defs, audio_locks
            ),
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
        skipped = len(chars) - len(result_list)
        interface.print(f"Finished scraping: {len(result_list)} succeeded, {skipped} skipped")
        return result_list
