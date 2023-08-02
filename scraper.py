import requests_html

ses = requests_html.HTMLSession()


def scrapeWord(hanzi, numDefs, numExamples):
    info = dict()

    r = ses.get(
        "https://www.archchinese.com/chinese_english_dictionary.html?find=" + hanzi
    )
    r.html.render(sleep=0.5)

    # Get basic info
    charDef = (
        r.html.find("#charDef", first=True)
        .text.replace("\xa0", "")
        .replace("»", "")
        .split("\n")
    )

    details = dict()

    for detail in charDef:
        x = detail.split(":")
        if len(x) >= 2:
            details[x[0].strip()] = x[1].strip()

    info["definition"] = ", ".join(details["Definition"].split(", ")[:numDefs])
    pinyinLst = details["Pinyin"].split(", ")
    info["pinyin"] = pinyinLst[0]
    info["pinyin2"] = ", ".join(pinyinLst[1:])
    info["hsk"] = details["HSK Level"]
    info["formation"] = details["Formation"]

    # Get examples
    wordTable = r.html.find("#wordPaneContent #wordTable", first=True)
    exWords = wordTable.find(".word-container .char-effect:first-child")
    exInfo = wordTable.find(".col-md-7")

    examples = []
    for i in range(numExamples):
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

    info["examples"] = examples
    return info


print(scrapeWord("你", 3, 3))
