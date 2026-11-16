"""Tk frontend. All widgets are accessed only by the main Tk thread."""
import logging
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .anki_connect import AnkiConnect
from .application import Application
from .config import GenerationOptions, RunRequest

MODES = {"Anki deck": "anki", "CSV": "csv", "Update existing deck": "update"}


class Window:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.catalog_loaded = False
        self.controls = []
        defaults = GenerationOptions()
        root.title("AnkiChinese")
        root.geometry("800x760")
        root.minsize(680, 650)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame = ttk.Frame(root, padding=12)
        frame.grid(sticky="nsew")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(8, weight=1)
        ttk.Label(frame, text="AnkiChinese", font=("TkDefaultFont", 20)).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="Output").grid(row=1, column=0, sticky="w")
        self.mode = tk.StringVar(value="Anki deck")
        mode_box = ttk.Combobox(frame, textvariable=self.mode, values=list(MODES), state="readonly")
        mode_box.grid(row=1, column=1, sticky="ew", pady=6)
        self.controls.append((mode_box, "readonly"))
        mode_box.bind("<<ComboboxSelected>>", self.change_mode)
        ttk.Label(frame, text="Characters").grid(row=2, column=0, sticky="nw")
        self.characters = tk.Text(frame, height=5, wrap="char")
        self.characters.grid(row=2, column=1, sticky="ew")
        self.controls.append((self.characters, "normal"))
        self.add_button(frame, "Import file…", self.import_characters, 2, 2)
        self.output_frame = ttk.Frame(frame)
        self.output_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
        self.output_frame.columnconfigure(1, weight=1)
        ttk.Label(self.output_frame, text="Output file").grid(row=0, column=0)
        self.output_path = tk.StringVar(value=str(Path.cwd() / "ankichinese_output.apkg"))
        self.add_entry(self.output_frame, self.output_path, 0, 1)
        self.add_button(self.output_frame, "Browse…", self.browse_output, 0, 2)
        self.target_frame = ttk.LabelFrame(frame, text="Anki collection", padding=6)
        self.target_frame.columnconfigure(1, weight=1)
        ttk.Label(self.target_frame, text="Deck").grid(row=0, column=0, sticky="w")
        self.deck_name = tk.StringVar()
        self.deck_box = ttk.Combobox(self.target_frame, textvariable=self.deck_name, state="readonly")
        self.deck_box.grid(row=0, column=1, sticky="ew")
        ttk.Label(self.target_frame, text="Note type").grid(row=1, column=0, sticky="w")
        self.model_name = tk.StringVar()
        self.model_box = ttk.Combobox(self.target_frame, textvariable=self.model_name, state="readonly")
        self.model_box.grid(row=1, column=1, sticky="ew")
        self.controls.extend(((self.deck_box, "readonly"), (self.model_box, "readonly")))
        self.add_button(self.target_frame, "Refresh", self.refresh_collection, 0, 2)
        self.include_existing = tk.BooleanVar(value=False)
        include = ttk.Checkbutton(self.target_frame, text="Also process existing deck characters", variable=self.include_existing)
        include.grid(row=2, column=0, columnspan=3, sticky="w")
        self.controls.append((include, "normal"))
        self.connection_status = ttk.Label(self.target_frame, text="Open Anki with AnkiConnect installed")
        self.connection_status.grid(row=3, column=0, columnspan=3, sticky="w")
        options_frame = ttk.LabelFrame(frame, text="Options", padding=6)
        options_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=6)
        self.option_vars = {}
        for index, (name, label, value) in enumerate((
            ("definition_limit", "Maximum definitions", defaults.definition_limit),
            ("example_limit", "Example words", defaults.example_limit),
            ("audio_concurrency", "Concurrent audio downloads", defaults.audio_concurrency),
            ("audio_per_second", "Audio downloads per second", defaults.audio_per_second),
        )):
            row, column = divmod(index, 2)
            ttk.Label(options_frame, text=label).grid(row=row, column=column * 2, sticky="w", padx=5)
            variable = tk.StringVar(value=str(value))
            spin = ttk.Spinbox(options_frame, textvariable=variable, from_=1, to=100, width=7)
            spin.grid(row=row, column=column * 2 + 1, padx=5)
            self.option_vars[name] = variable
            self.controls.append((spin, "normal"))
        ttk.Label(options_frame, text="Audio cache").grid(row=2, column=0, sticky="w", padx=5)
        self.audio_cache_dir = tk.StringVar(value=str(defaults.audio_cache_dir))
        self.add_entry(options_frame, self.audio_cache_dir, 2, 1, columnspan=3)
        self.status = ttk.Label(frame, text="Ready")
        self.status.grid(row=5, column=0, columnspan=3, sticky="w")
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", pady=6)
        self.start_button = ttk.Button(frame, text="Start", command=self.start_run)
        self.start_button.grid(row=7, column=2, sticky="e")
        self.log = tk.Text(frame, state="disabled", height=12, wrap="word")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=6)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(50, self.process_events)

    def add_button(self, parent, text, command, row, column):
        button = ttk.Button(parent, text=text, command=command)
        button.grid(row=row, column=column, padx=5, pady=3)
        self.controls.append((button, "normal"))
        return button

    def add_entry(self, parent, variable, row, column, columnspan=1):
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=5)
        self.controls.append((entry, "normal"))
        return entry

    def change_mode(self, _event=None):
        update = MODES[self.mode.get()] == "update"
        if update:
            self.output_frame.grid_remove()
            self.target_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
            if not self.catalog_loaded:
                self.refresh_collection()
        else:
            self.target_frame.grid_remove()
            self.output_frame.grid()
            suffix = ".csv" if MODES[self.mode.get()] == "csv" else ".apkg"
            output = Path(self.output_path.get())
            if output.name and not output.is_dir():
                self.output_path.set(str(output.with_suffix(suffix)))

    def import_characters(self):
        filename = filedialog.askopenfilename(parent=self.root)
        if not filename:
            return
        try:
            self.characters.insert("end", Path(filename).read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Cannot read file", str(exc), parent=self.root)

    def browse_output(self):
        suffix = ".csv" if MODES[self.mode.get()] == "csv" else ".apkg"
        filename = filedialog.asksaveasfilename(parent=self.root, defaultextension=suffix, initialfile="ankichinese_output" + suffix)
        if filename:
            self.output_path.set(filename)

    def set_busy(self, busy):
        self.busy = busy
        self.start_button.configure(state="disabled" if busy else "normal")
        for control, state in self.controls:
            control.configure(state="disabled" if busy else state)

    def run_in_background(self, function, result_event):
        def target():
            try:
                self.events.put((result_event, function()))
            except Exception as exc:
                logging.exception("AnkiChinese task failed")
                self.events.put(("error", str(exc)))
        threading.Thread(target=target, daemon=True).start()

    def refresh_collection(self):
        if self.busy:
            return
        self.set_busy(True)
        self.connection_status.configure(text="Loading deck and note-type names…")
        def load():
            with AnkiConnect() as anki:
                decks = anki.decks()
                models = [name for name in anki.models() if "Hanzi" in anki.model_fields(name)]
            return decks, models
        self.run_in_background(load, "catalog")

    def start_run(self):
        if self.busy:
            return
        try:
            options = GenerationOptions(**{key: int(value.get()) for key, value in self.option_vars.items()}, audio_cache_dir=Path(self.audio_cache_dir.get()))
            request = RunRequest(self.characters.get("1.0", "end"), MODES[self.mode.get()], options,
                                 Path(self.output_path.get()), self.deck_name.get(), self.model_name.get(), self.include_existing.get())
        except (ValueError, OSError) as exc:
            messagebox.showerror("Check options", str(exc), parent=self.root)
            return
        self.set_busy(True)
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.app = Application()
        report = lambda event: self.events.put(("progress", event))
        self.run_in_background(lambda: self.app.prepare(request, report), "prepared")

    def append_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def process_events(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "catalog":
                decks, models = value
                self.deck_box.configure(values=decks)
                self.model_box.configure(values=models)
                if self.deck_name.get() not in decks:
                    self.deck_name.set(decks[0] if decks else "")
                if self.model_name.get() not in models:
                    self.model_name.set(models[0] if models else "")
                self.catalog_loaded = True
                self.connection_status.configure(text="Connected; collection notes load when you start")
                self.set_busy(False)
            elif kind == "progress":
                suffix = " ({}/{})".format(value.completed, value.total) if value.total else ""
                self.status.configure(text=value.message + suffix)
                self.progress.configure(maximum=max(value.total, 1), value=value.completed)
                if not value.total:
                    self.append_log(value.message)
            elif kind == "prepared":
                if value.plan:
                    self.append_log(value.plan.summary())
                    if value.plan.has_changes and not messagebox.askokcancel("Apply Anki update", value.plan.summary(), parent=self.root):
                        self.append_log("Update canceled")
                        self.status.configure(text="Canceled")
                        self.app.close()
                        self.set_busy(False)
                        continue
                report = lambda event: self.events.put(("progress", event))
                self.run_in_background(lambda run=value: self.app.apply(run, report), "finished")
            elif kind == "finished":
                self.app.close()
                self.set_busy(False)
            elif kind == "error":
                if hasattr(self, "app"):
                    self.app.close()
                self.append_log(value)
                self.status.configure(text="Stopped: " + value)
                self.connection_status.configure(text="")
                self.set_busy(False)
        self.root.after(50, self.process_events)

    def close(self):
        if self.busy:
            messagebox.showinfo("Task running", "Wait for the current task to finish before closing.", parent=self.root)
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    Window(root)
    root.mainloop()


if __name__ == "__main__":
    main()
