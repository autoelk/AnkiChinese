"""Read cached recordings or download them atomically from audio-cmn."""
import os
import html
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
from ..pinyin import to_tone_marks

AUDIO_CMN_URL = "https://raw.githubusercontent.com/hugolpz/audio-cmn/master/64k/syllabs/cmn-{}.mp3"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
SOURCE_KEYS = {"ju4": "jv4"}
USER_AGENT = "AnkiChinese/1.0 (https://github.com/autoelk/AnkiChinese)"


def audio_key(reading):
    key = reading.lower().replace("u:", "v").replace("ü", "v")
    return key if re.fullmatch(r"[a-z]+[1-5]", key) else ""


class AudioStore:

    def __init__(self, cache_dir, legacy_cache_dir=None, download=None):
        self.cache_dir = Path(cache_dir)
        self.legacy_cache_dir = Path(legacy_cache_dir) if legacy_cache_dir else Path.cwd() / "ankichinese_audio"
        self.download = download or requests.get
        self._fallback_notices = {}

    @property
    def NOTICE_PATHS(self):
        primary = Path(__file__).resolve().parent.parent / "data/AUDIO_CMN_NOTICE.txt"
        return (primary, *[self._fallback_notices[name] for name in sorted(self._fallback_notices)])

    def cached_path(self, key):
        if not re.fullmatch(r"[a-z]+[1-5]", key):
            return None
        for cache_dir in (self.cache_dir, self.legacy_cache_dir):
            for filename_key in dict.fromkeys((key, SOURCE_KEYS.get(key, key))):
                path = cache_dir / "cmn-{}.mp3".format(filename_key)
                if path.is_file() and path.stat().st_size:
                    return path
            path = cache_dir / "commons-{}.ogg".format(key)
            notice = cache_dir / "commons-{}-NOTICE.txt".format(key)
            if path.is_file() and path.stat().st_size and notice.is_file():
                self._fallback_notices[notice.name] = notice
                return path
        return None

    def get_recordings(self, readings, max_concurrent, max_per_second):
        """Return recordings under the caller's readings, hiding source filenames."""
        readings_by_key = {}
        for reading in dict.fromkeys(readings):
            key = audio_key(reading)
            if not key:
                yield reading, None, "No recording available"
            else:
                readings_by_key.setdefault(key, []).append(reading)
        for key, path, error in self._recordings_by_key(readings_by_key, max_concurrent, max_per_second):
            for reading in readings_by_key[key]:
                yield reading, path, error

    def _recordings_by_key(self, keys, max_concurrent, max_per_second):
        """Yield cached/downloaded recordings once per key, with bounded requests."""
        pending_keys = []
        for key in dict.fromkeys(keys):
            path = self.cached_path(key)
            if path:
                yield key, path, ""
            else:
                pending_keys.append(key)
        lock = threading.Lock()
        next_start = 0

        def download(key):
            nonlocal next_start
            with lock:
                time.sleep(max(0, next_start - time.monotonic()))
                next_start = time.monotonic() + 1 / max_per_second
            return self.get_recording(key)

        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(download, key): key for key in pending_keys}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    path = future.result()
                    yield key, path, "" if path else "No recording available"
                except OSError as exc:
                    yield key, None, str(exc)

    def get_recording(self, key):
        cached_path = self.cached_path(key)
        if cached_path or not re.fullmatch(r"[a-z]+[1-5]", key):
            return cached_path
        source_error = None
        try:
            response = self.download(AUDIO_CMN_URL.format(SOURCE_KEYS.get(key, key)), timeout=(5, 20))
            if response.status_code != 404:
                response.raise_for_status()
                if not response.content:
                    raise OSError("The recording was empty")
                return self._cache_bytes("cmn-{}.mp3".format(key), response.content)
        except (requests.RequestException, OSError) as exc:
            source_error = exc
        try:
            fallback = self._commons_recording(key)
        except requests.RequestException as exc:
            raise OSError(str(exc)) from exc
        if fallback:
            return fallback
        if source_error:
            raise OSError(str(source_error)) from source_error
        return None

    def _commons_recording(self, key):
        title = "File:Zh-{}.ogg".format(to_tone_marks(key))
        response = self.download(COMMONS_API_URL, params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|extmetadata", "titles": title,
        }, headers={"User-Agent": USER_AGENT}, timeout=(5, 20))
        response.raise_for_status()
        try:
            pages = response.json()["query"]["pages"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OSError("Invalid Wikimedia Commons audio response") from exc
        if not isinstance(pages, dict):
            raise OSError("Invalid Wikimedia Commons audio response")
        for page in pages.values():
            images = page.get("imageinfo", [])
            if not images:
                continue
            image = images[0]
            metadata = image.get("extmetadata", {})
            def plain_metadata(name):
                return html.unescape(re.sub(r"<[^>]+>", "", metadata.get(name, {}).get("value", "")))
            author = plain_metadata("Artist")
            license_name = plain_metadata("LicenseShortName")
            license_url = plain_metadata("LicenseUrl")
            if not author or not license_name or not license_url:
                raise OSError("Wikimedia recording has incomplete attribution metadata")
            url = image["url"].split("?")[0]
            audio = self.download(url, params={"download": "1"}, headers={"User-Agent": USER_AGENT}, timeout=(5, 20))
            audio.raise_for_status()
            if not audio.content.startswith(b"OggS"):
                raise OSError("Wikimedia returned an invalid Ogg recording")
            notice_name = "commons-{}-NOTICE.txt".format(key)
            attribution = "\n".join((
                "Wikimedia Commons pronunciation recording", title, "Author: " + author,
                "License: " + license_name, license_url,
                image.get("descriptionurl", "https://commons.wikimedia.org/wiki/" + title),
                "Source audio: " + url, "Downloaded without audio modification.", "",
            ))
            notice = self._cache_bytes(notice_name, attribution.encode("utf-8"))
            path = self._cache_bytes("commons-{}.ogg".format(key), audio.content)
            self._fallback_notices[notice_name] = notice
            return path
        return None

    def _cache_bytes(self, filename, content):
        temporary_path = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False) as output:
                temporary_path = Path(output.name)
                output.write(content)
            path = self.cache_dir / filename
            os.replace(temporary_path, path)
            return path
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
