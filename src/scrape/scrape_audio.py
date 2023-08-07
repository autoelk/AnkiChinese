import requests
import os
from tqdm import tqdm


def scrape(list_of_pinyin):
    with requests.Session() as req:
        for pinyin in tqdm(list_of_pinyin):
            r = req.get(f"https://cdn.yoyochinese.com/audio/pychart/{pinyin}.mp3")
            if r.status_code == 404:
                r = req.get(f"https://www.purpleculture.net/mp3/{pinyin}.mp3")
            file = f"ankichinese_audio/{pinyin}.mp3"
            os.makedirs(os.path.dirname(file), exist_ok=True)
            with open(file, "wb") as f:
                f.write(r.content)


def cli():
    list_of_pinyin = []
    with open("pinyin_tones.txt", encoding="utf8", errors="replace", mode="r") as f:
        for pinyin in f:
            list_of_pinyin.append(pinyin.strip())
    scrape(list_of_pinyin)


if __name__ == "__main__":
    cli()
