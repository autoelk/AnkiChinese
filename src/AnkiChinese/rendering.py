"""Convert structured content to Anki/CSV fields at the output boundary."""
from html import escape
from .pinyin import to_tone_marks

NOTE_FIELDS = (
    "Hanzi", "Traditional", "Definition", "Pinyin", "Examples", "Formation",
    "Frequency Rank", "Frequency Count", "HSK", "Audio", "Writing Hints",
)


def render_fields(card):
    examples, hints = [], []
    for example in card.examples:
        pronunciation = escape(" ".join(to_tone_marks(token) for token in example.pronunciation))
        definitions = escape(", ".join(example.definitions))
        examples.append("{}[{}]: {}".format(escape(example.word), pronunciation, definitions))
        hints.append("<b>{}</b>: {}".format(pronunciation, definitions))
    return {
        "Hanzi": escape(card.character), "Traditional": escape(card.traditional),
        "Definition": escape(", ".join(card.definitions)),
        "Pinyin": escape(", ".join(to_tone_marks(token) for token in card.readings)),
        "Examples": "<br>".join(examples), "Writing Hints": "<br>".join(hints),
        "Formation": escape(card.formation), "HSK": card.hsk_level,
        "Frequency Rank": "" if card.frequency_rank is None else str(card.frequency_rank),
        "Frequency Count": "" if card.frequency_per_million is None else str(card.frequency_per_million),
        "Audio": "[sound:{}]".format(card.audio_path.name) if card.audio_path else "",
    }
