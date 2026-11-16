import re


TONE_MARKS = {
    "a": "āáǎà",
    "e": "ēéěè",
    "i": "īíǐì",
    "o": "ōóǒò",
    "u": "ūúǔù",
    "ü": "ǖǘǚǜ",
}


def to_tone_marks(token: str) -> str:
    """Convert one tone-number syllable to tone-mark pinyin."""
    token = token.strip().lower().replace("u:", "ü").replace("v", "ü")
    match = re.fullmatch(r"(.+?)([1-5])", token)
    if not match:
        return token
    syllable, tone_text = match.groups()
    tone = int(tone_text)
    if tone == 5:
        return syllable

    if "a" in syllable:
        target = syllable.index("a")
    elif "e" in syllable:
        target = syllable.index("e")
    elif "ou" in syllable:
        target = syllable.index("o")
    else:
        vowel_positions = [i for i, char in enumerate(syllable) if char in TONE_MARKS]
        if not vowel_positions:
            return syllable
        target = vowel_positions[-1]

    vowel = syllable[target]
    marked = TONE_MARKS[vowel][tone - 1]
    return syllable[:target] + marked + syllable[target + 1:]

