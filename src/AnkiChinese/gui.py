from tkinter import *
from tkinter import ttk
from tkinter import font
from tkinter import filedialog

import sys
import os.path
import re as regex
import asyncio
import threading

sys.path.insert(1, os.path.dirname(__file__))  # allows python to find other modules

import scraper
import export
from ankipandas import Collection


class Page(ttk.Frame):
    def __init__(self, root):
        ttk.Frame.__init__(self, root)

    def show(self):
        self.lift()

    def update(self):
        pass


class MainMenuPage(Page):
    def __init__(self, root, controller):
        Page.__init__(self, root)
        self.name = "MainMenu"

        menu_text_frame = ttk.Frame(self)
        menu_text_frame.grid(row=0, column=0)

        ttk.Label(menu_text_frame, text="AnkiChinese", font=controller.h1_font).grid(
            row=0, column=0
        )
        ttk.Label(
            menu_text_frame, text="Chinese Flashcard Generator", font=controller.h3_font
        ).grid(row=1, column=0)

        buttons = ttk.Frame(self)
        buttons.grid(row=1, column=0)
        ttk.Label(buttons, text="Select a mode:").grid(row=0, column=0, columnspan=2)
        ttk.Button(
            buttons, text="CSV", command=lambda: controller.show_page("CSV")
        ).grid(row=1, column=0, padx=5)
        ttk.Label(
            buttons, text="Generate a CSV file containing information on characters"
        ).grid(row=1, column=1, sticky=W)
        ttk.Button(
            buttons, text="Anki", command=lambda: controller.show_page("AnkiDeck")
        ).grid(row=2, column=0, padx=5)
        ttk.Label(buttons, text="Generate a new Anki deck with special features").grid(
            row=2, column=1, sticky=W
        )
        ttk.Button(
            buttons, text="Update", command=lambda: controller.show_page("Update")
        ).grid(row=3, column=0, padx=5)
        ttk.Label(
            buttons, text="Update existing Anki deck without losing progress"
        ).grid(row=3, column=1, sticky=W)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)


class AnkiDeckPage(Page):
    def __init__(self, root, controller):
        Page.__init__(self, root)
        self.name = "AnkiDeck"

        title_frame = ttk.Frame(self)
        title_frame.grid(row=0, column=0)
        ttk.Label(title_frame, text="Anki Deck", font=controller.h2_font).grid(
            row=0, column=0
        )
        ttk.Label(
            title_frame,
            text="Generate a new Anki deck with custom AnkiChinese features",
        ).grid(row=1, column=0)

        basic_options_frame = ttk.Frame(self)
        basic_options_frame.grid(row=1, column=0)

        # Characters to scrape
        ttk.Label(basic_options_frame, text="Characters").grid(row=0, column=0, stick=W)
        self.char_text_box = Text(basic_options_frame, width=40, height=10)
        self.char_text_box.grid(row=1, column=0, sticky=W)
        ttk.Button(basic_options_frame, text="Import", command=self.import_chars).grid(
            row=1, column=1, sticky=SW
        )

        # Output file location
        ttk.Label(basic_options_frame, text="Output file location").grid(
            row=2, column=0, sticky=W
        )
        self.output = StringVar(self)
        self.output_entry = ttk.Entry(
            basic_options_frame,
            textvariable=self.output,
            width=30,
            validate="focusout",
            validatecommand=(
                self.register(self.validate_output),
                "%P",
                "%V",
            ),
        )
        self.output_entry.grid(row=3, column=0, sticky=W)
        ttk.Button(basic_options_frame, text="Browse", command=self.get_output).grid(
            row=3, column=1, sticky=W
        )
        self.output_error_msg = StringVar(self)
        ttk.Label(
            basic_options_frame,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.output_error_msg,
        ).grid(row=4, column=0, sticky=W)

        # ADVANCED OPTIONS SECTION
        advanced_options_frame = ttk.Labelframe(self, text="Advanced Options")
        advanced_options_frame.grid(row=2, column=0)

        ttk.Label(advanced_options_frame, text="# of definitions").grid(
            row=0, column=0, padx=5, sticky=W
        )
        self.num_defs = StringVar(self)
        ttk.Spinbox(
            advanced_options_frame,
            from_=1,
            to=10,
            increment=1,
            textvariable=self.num_defs,
            width=15,
        ).grid(row=1, column=0, padx=5)

        ttk.Label(advanced_options_frame, text="# of examples").grid(
            row=2, column=0, padx=5, sticky=W
        )
        self.num_examples = StringVar(self)
        ttk.Spinbox(
            advanced_options_frame,
            from_=1,
            to=10,
            increment=1,
            textvariable=self.num_examples,
            width=15,
        ).grid(row=3, column=0, padx=5)

        ttk.Label(advanced_options_frame, text="Max requests at once").grid(
            row=0, column=1, padx=5, sticky=W
        )
        self.max_requests_at_once = StringVar(self)
        ttk.Spinbox(
            advanced_options_frame,
            from_=1,
            to=10,
            increment=1,
            textvariable=self.max_requests_at_once,
            width=15,
        ).grid(row=1, column=1, padx=5)

        ttk.Label(advanced_options_frame, text="Max requests per second").grid(
            row=2, column=1, padx=5, sticky=W
        )
        self.max_requests_per_second = StringVar(self)
        ttk.Spinbox(
            advanced_options_frame,
            from_=1,
            to=10,
            increment=1,
            textvariable=self.max_requests_per_second,
            width=15,
        ).grid(row=3, column=1, padx=5)

        # Navigation buttons
        nav_buttons_frame = ttk.Frame(self)
        nav_buttons_frame.grid(row=3, column=0, sticky=SE)

        ttk.Button(
            nav_buttons_frame,
            text="Back",
            command=lambda: controller.show_page("MainMenu"),
        ).grid(row=0, column=0, padx=5, pady=5)
        self.next_button = ttk.Button(
            nav_buttons_frame,
            text="Next",
            command=self.update_controller,
        )
        self.next_button.grid(row=0, column=1, padx=5, pady=5)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def update(self):
        # Set default values
        self.num_defs.set("5")
        self.num_examples.set("5")
        self.max_requests_at_once.set("5")
        self.max_requests_per_second.set("5")
        self.output.set(os.path.join(os.getcwd(), "ankichinese_output.apkg"))

    def import_chars(self):
        input_file = filedialog.askopenfilename()
        content = ""
        try:
            with open(input_file, encoding="utf8", errors="replace", mode="r") as f:
                for line in f:
                    content += line
        except FileNotFoundError as e:
            print(e)

        self.char_text_box.insert("1.0", content)

    def get_output(self):
        self.output.set(
            filedialog.asksaveasfilename(
                defaultextension="apkg",
                initialfile="ankichinese_output",
            )
        )
        self.output_entry.validate()

    def validate_output(self, new_val, operation):
        valid = regex.search(r"[^\/]+(?=\.apkg$)", new_val) is not None
        if valid:
            self.output_error_msg.set("")
        else:
            self.output_error_msg.set("Invalid file location")
        return valid

    def update_controller(self):
        controller.export_mode = "AnkiDeck"
        controller.chars = set(
            [
                char
                for char in self.char_text_box.get("1.0", "end")
                if not char.isspace()
            ]
        )
        controller.requests_at_once = int(self.max_requests_at_once.get())
        controller.requests_per_second = int(self.max_requests_per_second.get())
        controller.num_examples = int(self.num_examples.get())
        controller.num_definitions = int(self.num_defs.get())
        controller.output = self.output.get()
        controller.show_page("Generator")


class GeneratorPage(Page):
    def __init__(self, root, controller):
        Page.__init__(self, root)
        self.name = "Generator"

        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, stick=NSEW)
        ttk.Label(main_frame, text="Summary", font=controller.h2_font).grid(
            row=0, column=0, pady=5
        )
        self.log_text_box = Text(main_frame)
        self.log_text_box.grid(row=1, column=0, padx=5, sticky=NSEW)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Navigation buttons
        nav_buttons_frame = ttk.Frame(self)
        nav_buttons_frame.grid(row=1, column=0, sticky=S)

        self.progress_bar = ttk.Progressbar(
            nav_buttons_frame, orient=HORIZONTAL, length=200, mode="determinate"
        )
        self.progress_bar.grid(row=0, column=0, sticky=W)
        ttk.Button(
            nav_buttons_frame,
            text="Back",
            command=lambda: controller.show_page(controller.export_mode),
        ).grid(row=0, column=1, padx=5, pady=5, sticky=E)
        ttk.Button(
            nav_buttons_frame,
            text="Start",
            command=self.do_scrape_and_export,
        ).grid(row=0, column=2, padx=5, pady=5, sticky=E)
        self.progress_bar.bind(
            "<<StepProgressBar>>", lambda e: self.progress_bar.step(1)
        )
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def do_scrape_and_export(self):
        thread = threading.Thread(target=controller.scrape_and_export_wrapper)
        thread.start()


class Controller:
    def __init__(self, root):
        self.h1_font = font.Font(
            family="Helvetica", name="h1_font", size=72, weight="bold"
        )
        self.h2_font = font.Font(
            family="Helvetica", name="h2_font", size=48, weight="bold"
        )
        self.h3_font = font.Font(
            family="Helvetica", name="h3_font", size=24, weight="normal"
        )

        self.pages = {}
        self.add_page(MainMenuPage(root, self))
        self.add_page(AnkiDeckPage(root, self))
        self.add_page(GeneratorPage(root, self))

        self.export_mode = "AnkiDeck"
        self.chars = []
        self.requests_at_once = 5
        self.requests_per_second = 5
        self.num_examples = 5
        self.num_definitions = 5
        self.output = None

        self.scrape_loop = asyncio.new_event_loop()

    def add_page(self, page):
        self.pages[page.name] = page
        page.grid(row=0, column=0, sticky=NSEW)

    def get_page(self, name):
        page = self.pages.get(name)
        if page:
            return page

    def show_page(self, name):
        page = self.pages.get(name)
        if page:
            self.cur_page = name
            page.show()
            page.update()

    def scrape_and_export_wrapper(self):
        asyncio.set_event_loop(self.scrape_loop)
        self.scrape_loop.run_until_complete(self.scrape_and_export())

    async def scrape_and_export(self):
        if self.export_mode == "CSV":
            pass
        elif self.export_mode == "AnkiDeck":
            pbar = self.get_page("Generator").progress_bar
            pbar.configure(maximum=len(self.chars))

            results = await scraper.main(
                self.chars,
                self.requests_at_once,
                self.requests_per_second,
                self.num_examples,
                self.num_definitions,
                pbar,
            )

            export.gen_anki(results, self.output)
        elif self.export_mode == "Update":
            pass
        else:
            raise Exception("Unknown export mode")


if __name__ == "__main__":
    root = Tk()
    root.geometry("720x600")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.title("AnkiChinese")

    controller = Controller(root)
    controller.show_page("AnkiDeck")

    root.mainloop()
