import csv
from tqdm import tqdm
import requests_html

ses = requests_html.HTMLSession()


def scrapeChar(hanzi, numDefs, numExamples):
    info = dict()
    info["hanzi"] = hanzi

    r = ses.get(
        "https://www.archchinese.com/chinese_english_dictionary.html?find=" + hanzi
    )
    r.html.render(sleep=1)

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
            details[x[0].strip()] = x[1].strip()

    # Extract information we want
    info["definition"] = ", ".join(details["Definition"].split(", ")[:numDefs])
    pinyinLst = details["Pinyin"].split(", ")
    info["pinyin"] = pinyinLst[0]
    info["pinyin2"] = ", ".join(pinyinLst[1:]) if len(pinyinLst) > 1 else ""
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
        hanzi = exWords[i].text.strip()
        pinyin = exInfo[i + 1].find("p>a", first=True).text.strip()
        defn = ", ".join(
            exInfo[i + 1]
            .find("p", first=True)
            .text.split("\n")[0]
            .split("] ")[1]
            .split(", ")[:numDefs]
        )

        examples.append(hanzi + "[" + pinyin + "]: " + defn)

    info["examples"] = "<br>".join(examples) or ""
    return info


chars = []
with open("input.txt", encoding="utf8") as f:
    for line in f:
        for ch in line:
            if not ch.isspace():
                chars.append(ch)

with open("output.csv", "w", newline="", encoding="utf8") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(
        ["Hanzi", "Definition", "Pinyin", "Pinyin2", "HSK", "Formation", "Examples"]
    )

    for char in tqdm(chars):
        try:
            info = scrapeChar(char, 5, 3)
            writer.writerow(
                [
                    info["hanzi"],
                    info["definition"],
                    info["pinyin"],
                    info["pinyin2"],
                    info["hsk"],
                    info["formation"],
                    info["examples"],
                ]
            )
        except Exception as e:
            print("\nerror: " + char + " " + str(e))
