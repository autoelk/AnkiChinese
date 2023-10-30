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

    def set_default_vals(self):
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


class SpinboxField(ttk.Frame):
    def __init__(
        self,
        page,
        parent_frame,
        label,
        default_val=None,
        min_val=1,
        max_val=10,
        incr=1,
    ):
        ttk.Frame.__init__(self, parent_frame)
        self.grid()
        ttk.Label(self, text=label).grid(row=0, column=0, padx=5, sticky=W)
        self.page = page
        self.label = label
        self.value = StringVar(page)

        if default_val != None:
            self.value.set(str(default_val))
            self.valid = True
        else:
            self.valid = False

        self.spinbox = ttk.Spinbox(
            self,
            from_=min_val,
            to=max_val,
            increment=incr,
            textvariable=self.value,
            width=15,
            validate="focusout",
            validatecommand=(
                page.register(self.val_field),
                "%P",
            ),
        )
        self.spinbox.grid(row=1, column=0, padx=5)
        self.error_msg = StringVar(page)
        ttk.Label(
            self,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.error_msg,
        ).grid(row=2, column=0, sticky=W)

    def val_field(self, new_val):
        valid = new_val.isdigit() and 1 <= int(new_val) and int(new_val) <= 10
        self.error_msg.set("" if valid else "Invalid " + self.label)
        self.valid = valid
        self.page.update_next_btn_state()
        return valid


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

        basic_opt_frame = ttk.Frame(self)
        basic_opt_frame.grid(row=1, column=0)

        # Characters to scrape
        ttk.Label(basic_opt_frame, text="Characters").grid(row=0, column=0, stick=W)
        self.char_text_box = Text(basic_opt_frame, width=40, height=10)
        self.char_text_box.grid(row=1, column=0, sticky=W)
        ttk.Button(basic_opt_frame, text="Import", command=self.import_chars).grid(
            row=1, column=1, sticky=SW
        )

        # Output file location
        ttk.Label(basic_opt_frame, text="Output file location").grid(
            row=2, column=0, sticky=W
        )
        self.output = StringVar(self)
        self.output.set(os.path.join(os.getcwd(), "ankichinese_output.apkg"))
        self.output_entry = ttk.Entry(
            basic_opt_frame,
            textvariable=self.output,
            width=30,
            validate="focusout",
            validatecommand=(
                self.register(self.val_output),
                "%P",
            ),
        )
        self.output_valid = True
        self.output_entry.grid(row=3, column=0, sticky=W)
        ttk.Button(basic_opt_frame, text="Browse", command=self.get_output).grid(
            row=3, column=1, sticky=W
        )
        self.output_error_msg = StringVar(self)
        ttk.Label(
            basic_opt_frame,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.output_error_msg,
        ).grid(row=4, column=0, sticky=W)

        # ADVANCED OPTIONS SECTION
        adv_opt_frame = ttk.Labelframe(self, text="Advanced Options")
        adv_opt_frame.grid(row=2, column=0)

        # Number of Definitions
        self.num_defs = SpinboxField(self, adv_opt_frame, "# of definitions", 5)
        self.num_defs.grid(row=0, column=0)
        self.num_ex = SpinboxField(self, adv_opt_frame, "# of examples", 5)
        self.num_ex.grid(row=1, column=0)
        self.max_req_ps = SpinboxField(
            self, adv_opt_frame, "Max requests per second", 5
        )
        self.max_req_ps.grid(row=0, column=1)
        self.max_req_simul = SpinboxField(
            self, adv_opt_frame, "Max requests at once", 5
        )
        self.max_req_simul.grid(row=1, column=1)

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

    # validation helpers
    def val_output(self, new_val):
        valid = regex.search(r"[^\/]+(?=\.apkg$)", new_val) is not None
        self.output_error_msg.set("" if valid else "Invalid file location")
        self.output_valid = valid
        self.update_next_btn_state()
        return valid

    # enable next button if and only if all input fields are valid
    def update_next_btn_state(self):
        if (
            self.output_valid
            and self.num_ex.valid
            and self.num_defs.valid
            and self.max_req_ps.valid
            and self.max_req_simul.valid
        ):
            self.next_button.state(["!disabled"])
        else:
            self.next_button.state(["disabled"])

    def update_controller(self):
        controller.export_mode = "AnkiDeck"
        controller.chars = set(
            [
                char
                for char in self.char_text_box.get("1.0", "end")
                if not char.isspace()
            ]
        )
        controller.req_simul = int(self.max_req_simul.value.get())
        controller.req_ps = int(self.max_req_ps.value.get())
        controller.num_ex = int(self.num_ex.value.get())
        controller.num_defs = int(self.num_defs.value.get())
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
        for page in self.pages.values():
            page.set_default_vals()

        # default values
        self.export_mode = "AnkiDeck"
        self.chars = []
        self.req_simul = None
        self.req_ps = None
        self.num_ex = None
        self.num_defs = None
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

    def scrape_and_export_wrapper(self):
        asyncio.set_event_loop(self.scrape_loop)
        self.scrape_loop.run_until_complete(self.scrape_and_export())

    async def scrape_and_export(self):
        self.chars = list(filter(lambda char: "\u4e00" <= char <= "\u9fff", self.chars))

        if self.export_mode == "CSV":
            pbar = self.get_page("Generator").progress_bar
            pbar.configure(maximum=len(self.chars))

            results = await scraper.main(
                self.chars,
                self.req_simul,
                self.req_ps,
                self.num_ex,
                self.num_defs,
                pbar,
            )

            export.gen_csv(results, self.output)
        elif self.export_mode == "AnkiDeck":
            pbar = self.get_page("Generator").progress_bar
            pbar.configure(maximum=len(self.chars))

            results = await scraper.main(
                self.chars,
                self.req_simul,
                self.req_ps,
                self.num_ex,
                self.num_defs,
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
