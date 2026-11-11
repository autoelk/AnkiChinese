"""Client for the local AnkiConnect add-on API."""

import requests


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect is unavailable or rejects an action."""


class AnkiConnect:
    def __init__(self, url="http://127.0.0.1:8765", timeout=10):
        self.url = url
        self.timeout = timeout

    def invoke(self, action, **params):
        try:
            response = requests.post(
                self.url,
                json={"action": action, "version": 6, "params": params},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise AnkiConnectError(
                "Could not connect to AnkiConnect at {}. Open Anki, install the "
                "AnkiConnect add-on (code 2055492159), and try again.".format(self.url)
            ) from exc
        except ValueError as exc:
            raise AnkiConnectError("AnkiConnect returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise AnkiConnectError("AnkiConnect returned an invalid response.")
        if payload.get("error"):
            raise AnkiConnectError(
                "AnkiConnect action '{}' failed: {}".format(action, payload["error"])
            )
        return payload.get("result")

    def decks(self):
        return self.invoke("deckNames") or []

    def models(self):
        return self.invoke("modelNames") or []

    def deck_ids(self):
        return self.invoke("deckNamesAndIds") or {}

    def model_ids(self):
        return self.invoke("modelNamesAndIds") or {}

    def model_fields(self, model_name):
        return self.invoke("modelFieldNames", modelName=model_name) or []

    def model_templates(self, model_name):
        return self.invoke("modelTemplates", modelName=model_name) or {}

    def model_styling(self, model_name):
        return self.invoke("modelStyling", modelName=model_name) or {}

    @staticmethod
    def _quote_search(value):
        return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))

    def notes(self, deck_name, model_name=None):
        # Anki's deck search includes subdecks.
        query = "deck:{}".format(self._quote_search(deck_name))
        if model_name:
            query += " note:{}".format(self._quote_search(model_name))
        note_ids = self.invoke("findNotes", query=query) or []
        notes = []
        for start in range(0, len(note_ids), 500):
            batch = note_ids[start : start + 500]
            notes.extend(self.invoke("notesInfo", notes=batch) or [])
        return notes
