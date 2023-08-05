from requests_html import AsyncHTMLSession
import pandas as pd
import time


def cleanStr(string):
    return string.strip().replace("\n", "")


async def fetch(hanzi):
    r = await asession.get(
        "https://www.archchinese.com/chinese_english_dictionary.html?find=" + hanzi
    )
    await r.html.arender(sleep=5, timeout=30)

    return r


def scrapeWord(r, numDefs=5, numExamples=3):
    # Get basic info
    charDef = (
        r.html.find("#charDef", first=True)
        .text.replace("\xa0", "")
        .replace("»", "")
        .split("\n")
    )

    # Get all information on page
    details = dict()
    for detail in charDef:
        x = detail.split(":")
        if len(x) >= 2:
            details[cleanStr(x[0])] = cleanStr(x[1])

    info = dict()
    # Extract information we want
    info["definition"] = cleanStr(
        ", ".join(details["Definition"].split(", ")[:numDefs])
    )
    pinyinLst = details["Pinyin"].split(", ")
    info["pinyin"] = cleanStr(pinyinLst[0])

    # The following details may not always be available
    info["pinyin2"] = cleanStr(", ".join(pinyinLst[1:])) if len(pinyinLst) > 1 else ""
    if "HSK Level" in details:
        info["hsk"] = details["HSK Level"]
    else:
        info["hsk"] = ""
    if "Formation" in details:
        info["formation"] = details["Formation"]
    else:
        info["formation"] = ""

    # Get examples
    wordTable = r.html.find("#wordPaneContent #wordTable", first=True)
    exWords = wordTable.find(".word-container .char-effect:first-child")
    exInfo = wordTable.find(".col-md-7")

    examples = []
    for i in range(min(numExamples, len(exWords))):
        hanzi = exWords[i].text
        pinyin = exInfo[i + 1].find("p>a", first=True).text
        defn = ", ".join(
            exInfo[i + 1]
            .find("p", first=True)
            .text.split("\n")[0]
            .split("] ")[1]
            .split(", ")[:numDefs]
        )

        examples.append(hanzi + "[" + pinyin + "]: " + defn)

    info["examples"] = cleanStr("<br>".join(examples))
    return info


start = time.perf_counter()
list_of_hanzi = []  # unfinished list of characters to scrape
with open("input.txt", encoding="utf8", mode="r") as f:
    for line in f:
        for hanzi in line:
            if not hanzi.isspace():
                list_of_hanzi.append(hanzi)

print(
    f"Finished reading input in {time.perf_counter() - start} seconds, now fetching..."
)

asession = AsyncHTMLSession()
tasks = [lambda hanzi=hanzi: fetch(hanzi) for hanzi in list_of_hanzi]
results = asession.run(*tasks)
asession.close()

print(
    f"Finished fetching {len(list_of_hanzi)} pages in {time.perf_counter() - start} seconds, now parsing..."
)

for result in results:
    print(scrapeWord(result))

# df = pd.DataFrame.from_dict(results)

# df.to_csv("output.csv", index=False, encoding="utf8")
print(f"Finished in {time.perf_counter() - start} seconds")
