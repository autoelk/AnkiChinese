import asyncio
import aiometer
import functools

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

import pandas as pd
import re as regex
import time


def cleanStr(string):
    return regex.sub(" +", " ", string.strip().replace("\n", ""))


def scrapeWord(r, hanzi, numDefs=5, numExamples=3):
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


async def fetch(context, hanzi):
    page = await context.new_page()
    await page.goto(
        f"https://www.archchinese.com/chinese_english_dictionary.html?find={hanzi}"
    )
    await page.wait_for_function("() => !!document.querySelector('#wordTable')")
    content = await page.content()
    await page.close()
    return scrapeWord(content, hanzi)


async def main(chars):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        tasks = [functools.partial(fetch, context, hanzi) for hanzi in chars]
        return await aiometer.run_all(tasks, max_at_once=10, max_per_second=5)


start = time.perf_counter()
list_of_hanzi = []  # unfinished list of characters to scrape
with open("input.txt", encoding="utf8", mode="r") as f:
    for line in f:
        for hanzi in line:
            if not hanzi.isspace():
                list_of_hanzi.append(hanzi)

results = asyncio.run(main(list_of_hanzi))

df = pd.DataFrame(results)
df.to_csv("output.csv", index=False)

print(f"Finished in {time.perf_counter() - start} seconds")
