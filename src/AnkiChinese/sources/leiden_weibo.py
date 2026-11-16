"""Leiden Weibo word frequencies from the January 2012 corpus."""
import csv
import hashlib
import io
import json
import tempfile
import zipfile
from collections import Counter
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "LWC-word-frequencies.zip"
NOTICE_PATHS = (DATA_DIR / "LWC_NOTICE.txt",)
PER_MILLION = 1_000_000
DOWNLOAD_URL = "https://leidenweibocorpus.nl/download?file=words"


def import_archive(source_path, output_path=DATA_PATH):
    """Convert the original MySQL CSV dump into a compact word/count archive."""
    source_path, output_path = Path(source_path), Path(output_path)
    counts = Counter()
    with zipfile.ZipFile(source_path) as archive:
        with archive.open("words_types.txt") as source:
            reader = csv.reader(io.TextIOWrapper(source, encoding="utf-8"),
                                escapechar="\\", doublequote=False)
            for row in reader:
                if len(row) != 4 or not row[1]:
                    raise ValueError("Invalid row in Leiden Weibo word archive")
                count = int(row[3])
                if count < 0:
                    raise ValueError("Negative count in Leiden Weibo word archive")
                counts[row[1]] += count
    total = sum(counts.values())
    if not counts or total <= 0:
        raise ValueError("Leiden Weibo word archive contains no occurrences")
    metadata = {
        "source": DOWNLOAD_URL,
        "corpus_period": "2012-01",
        "source_updated": "2012-03-20",
        "license": "CC-BY-NC-SA-3.0",
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "total_tokens": total,
        "word_types": len(counts),
    }
    # Preserve every token type so the per-million denominator matches the corpus.
    with tempfile.NamedTemporaryFile(dir=output_path.parent, suffix=".tmp", delete=False) as target:
        temporary = Path(target.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(metadata, indent=2))
            with archive.open("words.csv", "w") as target:
                with io.TextIOWrapper(target, encoding="utf-8", newline="") as text:
                    writer = csv.writer(text)
                    writer.writerow(("token", "count"))
                    writer.writerows(sorted(counts.items()))
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    load_word_scores.cache_clear()
    return metadata


@lru_cache(maxsize=1)
def load_word_scores():
    """Return occurrences per million across all tokens in the word table."""
    with zipfile.ZipFile(DATA_PATH) as archive:
        metadata = json.loads(archive.read("metadata.json"))
        total = metadata["total_tokens"]
        if total <= 0:
            raise ValueError("Invalid Leiden Weibo token total")
        with archive.open("words.csv") as source:
            rows = csv.DictReader(io.TextIOWrapper(source, encoding="utf-8", newline=""))
            return {row["token"]: PER_MILLION * int(row["count"]) / total for row in rows}
