import asyncio
import aiometer
import functools

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

import re as regex
from tqdm import tqdm

import requests
import os


def clean_string(string):
    return regex.sub(" +", " ", string.strip().replace("\n", ""))


def scrape_basic_info(soup, args):
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
            ", ".join(details.get("Definition", "").split(", ")[: args.examples])
        ),
        "Pinyin": clean_string(pinyin_list[0]),
        "Pinyin 2": clean_string(", ".join(pinyin_list[1:])),
        "HSK": details.get("HSK Level", "None"),
        "Formation": details.get("Formation", ""),
    }
    return info


def scrape_example_words(soup, args):
    word_table = soup.select_one("#wordPaneContent #wordTable")

    ex_words = word_table.select(".word-container .char-effect:first-child")
    ex_info = word_table.select(".col-md-7")

    examples = []
    for i in range(min(args.examples, len(ex_words))):
        word = ex_words[i].text
        ruby_list = []  # Pinyin to appear above word
        for part in ex_info[i + 1].select("p>a>span"):
            ruby_list.append(part.get_text())
        ruby_text = " ".join(ruby_list)
        defn = ", ".join(
            regex.sub(
                "[\[].*?[\]]", "", ex_info[i + 1].select_one("p").get_text()
            ).split(", ")[: args.definitions]
        )

        examples.append(word + "[" + ruby_text + "]: " + defn)

    return clean_string("<br>".join(examples))


def scrape_audio(soup, args):
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

    return f"[sound:{pinyin_tone}.mp3]"


def scrape_word(r, args, hanzi):
    soup = BeautifulSoup(r, "html5lib")

    info = dict()
    info["Hanzi"] = hanzi
    info.update(scrape_basic_info(soup, args))
    info["Examples"] = scrape_example_words(soup, args)
    info["Audio"] = scrape_audio(soup, args)

    return info


async def fetch(context, args, hanzi):
    page = await context.new_page()
    await page.goto(
        f"https://www.archchinese.com/chinese_english_dictionary.html?find={hanzi}"
    )
    await page.wait_for_function("() => !!document.querySelector('#wordTable')")
    content = await page.content()
    await page.close()
    try:
        return scrape_word(content, args, hanzi)
    except Exception as e:
        print(f"Error scraping {hanzi}: {e}")
        return None


async def main(chars, args):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        pbar = tqdm(total=len(chars))
        result_list = []
        async with aiometer.amap(
            functools.partial(fetch, context, args),
            chars,
            max_at_once=args.requests_at_once,
            max_per_second=args.requests_per_second,
        ) as results:
            async for data in results:
                if data is not None:
                    result_list.append(data)
                pbar.update(1)
        await browser.close()
        pbar.close()
        return result_list


def scrape(hanzi_list, args):
    return asyncio.run(main(hanzi_list, args))
