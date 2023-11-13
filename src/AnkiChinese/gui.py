from tkinter import *
from tkinter import ttk
from tkinter import font
from tkinter import filedialog
from tkinter import messagebox

import sys
import os.path
import re as regex
import asyncio
import threading

sys.path.insert(1, os.path.dirname(__file__))  # Allows python to find other modules

import scraper
import export
from interface import Interface
from ankipandas import Collection


class Page(ttk.Frame):
    def __init__(self, root):
        ttk.Frame.__init__(self, root)

    def show(self):
        self.lift()


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
        buttons.grid(row=1, column=0, sticky=N)
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


class ConfigPage(Page):
    def __init__(self, root, controller, name, desc, ext):
        Page.__init__(self, root)
        self.name = name
        self.ext = ext

        title_frame = ttk.Frame(self)
        title_frame.grid(row=0, column=0)
        ttk.Label(title_frame, text=name, font=controller.h2_font).grid(row=0, column=0)
        ttk.Label(
            title_frame,
            text=desc,
        ).grid(row=1, column=0)

        # Basic options section
        self.create_basic_opt()

        # Advanced options section
        self.create_adv_opt()

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

        self.val_chars()

        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_basic_opt(self):
        basic_opt_frame = ttk.Frame(self)
        basic_opt_frame.grid(row=1, column=0)

        # Characters to scrape
        ttk.Label(basic_opt_frame, text="Characters").grid(row=0, column=0, sticky=W)
        self.char_text_box = Text(basic_opt_frame, width=40, height=10)
        self.char_text_box.grid(row=1, column=0, sticky=W)
        ttk.Button(basic_opt_frame, text="Import", command=self.import_chars).grid(
            row=1, column=1, sticky=SW
        )
        self.char_text_box.bind("<Leave>", lambda e: self.val_chars())
        self.chars_valid = False
        self.chars_error_msg = StringVar(self)
        ttk.Label(
            basic_opt_frame,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.chars_error_msg,
        ).grid(row=2, column=0, sticky=W)

        # Output file location
        ttk.Label(basic_opt_frame, text="Output file location").grid(
            row=3, column=0, sticky=W
        )
        self.output = StringVar(self)
        self.output.set(os.path.join(os.getcwd(), "ankichinese_output." + self.ext))
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
        self.output_entry.grid(row=4, column=0, sticky=W)
        ttk.Button(basic_opt_frame, text="Browse", command=self.get_output).grid(
            row=4, column=1, sticky=W
        )
        self.output_error_msg = StringVar(self)
        ttk.Label(
            basic_opt_frame,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.output_error_msg,
        ).grid(row=5, column=0, sticky=W)

    def create_adv_opt(self):
        adv_opt_frame = ttk.Labelframe(self, text="Advanced Options")
        adv_opt_frame.grid(row=2, column=0, sticky=N)

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
        self.val_chars()

    def get_output(self):
        self.output.set(
            filedialog.asksaveasfilename(
                defaultextension=self.ext,
                initialfile="ankichinese_output",
            )
        )
        self.output_entry.validate()

    # Validation helpers
    def val_chars(self):
        content = self.char_text_box.get(1.0, "end-1c")
        valid = len(set(filter(lambda char: "\u4e00" <= char <= "\u9fff", content))) > 0
        self.chars_error_msg.set("" if valid else "Include at least one hanzi")
        self.chars_valid = valid
        self.update_next_btn_state()
        return valid

    def val_output(self, new_val):
        # Make sure output ends with correct extension
        valid = (
            regex.search(r"[^\/]+(?=\." + regex.escape(self.ext) + r"$)", new_val)
            is not None
        )
        self.output_error_msg.set("" if valid else "Invalid file location")
        self.output_valid = valid
        self.update_next_btn_state()
        return valid

    # Enable next button if and only if all input fields are valid
    def update_next_btn_state(self):
        if (
            self.chars_valid
            and self.output_valid
            and self.num_ex.valid
            and self.num_defs.valid
            and self.max_req_ps.valid
            and self.max_req_simul.valid
        ):
            self.next_button.state(["!disabled"])
        else:
            self.next_button.state(["disabled"])

    def update_controller(self):
        controller.export_mode = self.name
        controller.chars = self.char_text_box.get("1.0", END)
        controller.req_simul = int(self.max_req_simul.value.get())
        controller.req_ps = int(self.max_req_ps.value.get())
        controller.num_ex = int(self.num_ex.value.get())
        controller.num_defs = int(self.num_defs.value.get())
        controller.output = self.output.get()
        controller.show_page("Generator")


class UpdateConfigPage(ConfigPage):
    def __init__(self, root, controller):
        self.controller = controller
        ConfigPage.__init__(
            self,
            root,
            controller,
            "Update",
            "Update existing Anki deck without losing progress",
            None,
        )
        self.do_select_model()

    def create_basic_opt(self):
        basic_opt_frame = ttk.Frame(self)
        basic_opt_frame.grid(row=1, column=0)

        # Characters to scrape
        char_frame = ttk.Frame(basic_opt_frame)
        char_frame.grid(row=0, column=1)

        ttk.Label(char_frame, text="Characters").grid(row=0, column=0, padx=5, sticky=W)
        self.chars_valid = False
        self.chars_error_msg = StringVar(self)
        ttk.Label(
            char_frame,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.chars_error_msg,
        ).grid(row=0, column=1, sticky=W)

        self.char_text_box = Text(char_frame, width=30, height=12)
        self.char_text_box.grid(row=1, column=0, columnspan=2)
        self.char_text_box.bind("<Leave>", lambda e: self.val_chars())
        ttk.Button(char_frame, text="Import", command=self.import_chars).grid(
            row=2, column=0, columnspan=2, padx=5, sticky=EW
        )

        self.include_existing = IntVar()
        ttk.Checkbutton(
            basic_opt_frame,
            text="Include existing characters",
            variable=self.include_existing,
            onvalue=1,
            offvalue=0,
        ).grid(row=1, column=0, columnspan=3)
        self.include_existing.set(0)

        # Deck and Model
        deck_model_frame = ttk.Frame(basic_opt_frame)
        deck_model_frame.grid(row=0, column=0)

        # Display decks along with models it contains
        ttk.Label(deck_model_frame, text="Select deck & model").grid(
            row=0, column=0, padx=5, sticky=W
        )
        self.deck_tree = ttk.Treeview(deck_model_frame, selectmode=BROWSE, show="tree")
        self.deck_tree.grid(row=1, column=0, padx=5)

        # Display fields of selected model
        ttk.Label(deck_model_frame, text="Fields").grid(
            row=0, column=1, padx=5, sticky=W
        )
        self.field_tree = ttk.Treeview(deck_model_frame, selectmode=BROWSE, show="tree")
        self.field_tree.grid(row=1, column=1, padx=5)

        # Fields that AnkiChinese would modify
        target_fields = [
            "Hanzi",
            "Traditional",
            "Definition",
            "Pinyin",
            "Pinyin 2",
            "Examples",
            "Formation",
            "HSK",
            "Audio",
        ]

        # Get info for display
        self.controller.col = Collection()
        self.deck_names = self.controller.col.cards.list_decks()
        self.model_names = {}
        self.column_names = {}
        self.notes_in_deck = {}

        # Decks
        for deck_name in self.deck_names:
            self.deck_tree.insert("", END, deck_name, text=deck_name)
            # Get model names
            cards = self.controller.col.cards.merge_notes()
            cards_in_deck = cards[cards["cdeck"].str.startswith(deck_name)]
            self.notes_in_deck[deck_name] = self.controller.col.notes[
                self.controller.col.notes.nid.isin(cards_in_deck.nid)
            ]
            self.model_names[deck_name] = self.notes_in_deck[deck_name].list_models()

            # Insert models
            for model_name in self.model_names[deck_name]:
                # Create unique ID in case multiple decks have same model
                model_id = deck_name + "::" + model_name
                self.deck_tree.insert(deck_name, END, model_id, text=model_name)

                # Get column/field names, intially prefixed with "nfld_"
                self.column_names[model_id] = (
                    self.notes_in_deck[deck_name]
                    .copy()
                    .query(f"nmodel == '{model_name}'")
                    .fields_as_columns()
                    .filter(regex="^nfld_", axis="columns")
                    .columns.str.replace("nfld_", "")
                )

                # Insert fields
                for column_name in self.column_names[model_id]:
                    # Create unique ID in case multiple model_ids have same column_name
                    column_id = model_id + "::" + column_name
                    self.field_tree.insert(
                        "",
                        END,
                        column_id,
                        text=column_name,
                        tags=(
                            "hanzi" if column_name == "Hanzi" else "",
                            "modify" if column_name in target_fields else "",
                        ),
                    )
                    self.field_tree.detach(column_id)
            self.deck_tree.item(deck_name, open=TRUE)

        # Error messages
        self.field_tree.insert(
            "",
            END,
            "deck_not_model",
            text="Please select a model",
            tags="error",
        )
        self.field_tree.detach("deck_not_model")
        self.field_tree.insert(
            "",
            END,
            "no_hanzi",
            text='Model must contain "Hanzi"',
            tags="error",
        )
        self.field_tree.detach("no_hanzi")

        self.field_tree.tag_configure("hanzi", foreground="green")
        self.field_tree.tag_configure("error", foreground="red")
        self.field_tree.tag_configure("modify", foreground="blue")
        self.output_valid = False

        self.deck_tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.do_select_model(),
        )
        # Select first deck so that error message is visible on load
        self.deck_tree.focus(item=self.deck_names[0])

    def show_model_cols(self, model_id):
        # Error messages
        self.field_tree.detach("deck_not_model")
        self.field_tree.detach("no_hanzi")
        if model_id not in self.column_names:
            self.field_tree.move("deck_not_model", "", END)
        else:
            if "Hanzi" not in self.column_names[model_id]:
                self.field_tree.move("no_hanzi", "", END)

        # Attach fields with model_id detach others
        for deck_name in self.deck_names:
            for model_name in self.model_names[deck_name]:
                curr_model_id = deck_name + "::" + model_name
                for column_name in self.column_names[curr_model_id]:
                    if curr_model_id == model_id:
                        self.field_tree.move(
                            curr_model_id + "::" + column_name, "", END
                        )
                    else:
                        self.field_tree.detach(curr_model_id + "::" + column_name)

    def do_select_model(self):
        self.show_model_cols(self.deck_tree.focus())
        self.val_output(self.deck_tree.focus())

    def val_output(self, model_id):
        if model_id in self.column_names:
            valid = "Hanzi" in self.column_names[model_id]
        else:
            valid = False
        self.output_valid = valid
        self.update_next_btn_state()
        return valid

    def update_controller(self):
        controller.export_mode = self.name
        controller.req_simul = int(self.max_req_simul.value.get())
        controller.req_ps = int(self.max_req_ps.value.get())
        controller.num_ex = int(self.num_ex.value.get())
        controller.num_defs = int(self.num_defs.value.get())
        controller.output = self.deck_tree.focus().split("::", 2)

        controller.chars = self.char_text_box.get("1.0", END)
        if self.include_existing == 1:
            existing_chars = (
                self.notes_in_deck[controller.output[0]]
                .fields_as_columns()
                .nfld_Hanzi.to_list()
            )
            controller.chars += str(existing_chars)

        controller.show_page("Generator")


class GeneratorPage(Page):
    def __init__(self, root, controller):
        Page.__init__(self, root)
        self.name = "Generator"

        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, sticky=NSEW)

        ttk.Label(main_frame, text="Generate", font=controller.h2_font).grid(
            row=0, column=0, pady=5
        )
        self.log_text_box = Text(main_frame, state=DISABLED)
        self.log_text_box.grid(row=1, column=0, padx=5, sticky=NSEW)
        self.log_text_box.bind(
            "<1>", lambda e: self.log_text_box.focus_set()
        )  # Allow clicking into box on MacOS
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Navigation buttons
        nav_buttons_frame = ttk.Frame(self)
        nav_buttons_frame.grid(row=2, column=0, sticky=EW)

        self.progress_bar = ttk.Progressbar(
            nav_buttons_frame, orient=HORIZONTAL, mode="determinate"
        )
        self.progress_bar.grid(row=0, column=0, padx=10, sticky=EW)

        ttk.Button(
            nav_buttons_frame,
            text="Back",
            command=self.do_go_back,
        ).grid(row=0, column=1, padx=5, pady=5)
        self.start_button = ttk.Button(
            nav_buttons_frame,
            text="Start",
            command=self.do_scrape_and_export,
        )
        self.start_button.grid(row=0, column=2, padx=5, pady=5)
        self.finish_button = ttk.Button(
            nav_buttons_frame,
            text="Finish",
            command=root.destroy,
        )
        self.finish_button.grid(row=0, column=2, padx=5, pady=5)
        self.start_button.lift()
        self.start_button.state(["!disabled"])

        self.progress_bar.bind(
            "<<StartProgressBar>>", lambda e: self.start_button.state(["disabled"])
        )
        self.progress_bar.bind(
            "<<StepProgressBar>>", lambda e: self.progress_bar.step(1)
        )
        self.progress_bar.bind("<<FinishProgressBar>>", lambda e: self.do_finish())
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        nav_buttons_frame.grid_columnconfigure(0, weight=1)

    def do_go_back(self):
        controller.show_page(controller.export_mode)
        self.start_button.lift()

    def do_finish(self):
        self.start_button.state(["!disabled"])
        self.finish_button.lift()

    def do_scrape_and_export(self):
        thread = threading.Thread(target=controller.scrape_and_export_wrapper)
        thread.start()


class GUI(Interface):
    def __init__(self, pbar, text_box):
        self.pbar = pbar
        self.text_box = text_box

    def start_pbar(self, num):
        self.pbar.configure(maximum=num)
        self.pbar.event_generate("<<StartProgressBar>>")

    async def step_pbar(self):
        self.pbar.event_generate("<<StepProgressBar>>")

    def finish_pbar(self):
        self.pbar.event_generate("<<FinishProgressBar>>")

    def print(self, msg):
        self.text_box.configure(state="normal")
        self.text_box.insert(END, str(msg) + "\n")
        self.text_box.configure(state="disabled")

    def confirm(self, msg):
        return messagebox.askokcancel(message=msg, title="Confirm")


class Controller:
    def __init__(self, root):
        # Store fonts here so they can be accessed from anywhere, essentially working as global variables
        self.h1_font = font.Font(
            family="Helvetica", name="h1_font", size=72, weight="bold"
        )
        self.h2_font = font.Font(
            family="Helvetica", name="h2_font", size=48, weight="bold"
        )
        self.h3_font = font.Font(
            family="Helvetica", name="h3_font", size=24, weight="normal"
        )

        # Create and store pages in pages dictionary
        self.pages = {}
        self.add_page(MainMenuPage(root, self))
        self.add_page(
            ConfigPage(
                root,
                self,
                "CSV",
                "Generate a CSV file containing information on characters",
                "csv",
            )
        )
        self.add_page(
            ConfigPage(
                root,
                self,
                "AnkiDeck",
                "Generate a new Anki deck with special features",
                "apkg",
            )
        )
        self.add_page(UpdateConfigPage(root, self))
        self.add_page(GeneratorPage(root, self))

        self.interface = GUI(
            self.get_page("Generator").progress_bar,
            self.get_page("Generator").log_text_box,
        )

        # Default values
        self.export_mode = "AnkiDeck"
        self.chars = []
        self.req_simul = None
        self.req_ps = None
        self.num_ex = None
        self.num_defs = None
        self.output = None

        # Create event loop for threading later
        self.scrape_loop = asyncio.new_event_loop()

    def add_page(self, page):
        self.pages[page.name] = page
        page.grid(row=0, column=0, sticky=NSEW)  # Make page frame fill window

    def get_page(self, name):
        page = self.pages.get(name)  # Check that page exists
        if page:
            return page

    def show_page(self, name):
        page = self.pages.get(name)  # Check that page exists
        if page:
            self.cur_page = name
            page.show()

    def scrape_and_export_wrapper(self):
        # Run scrape and export asynchronsouly so that GUI does not freeze
        asyncio.set_event_loop(self.scrape_loop)
        self.scrape_loop.run_until_complete(self.scrape_and_export())

    async def scrape_and_export(self):
        # Filter for only unique chinese characters
        self.chars = list(
            filter(lambda char: "\u4e00" <= char <= "\u9fff", set(self.chars))
        )

        results = await scraper.main(
            self.chars,
            self.req_simul,
            self.req_ps,
            self.num_ex,
            self.num_defs,
            self.interface,
        )

        if self.export_mode == "CSV":
            export.gen_csv(self.interface, results, self.output)
        elif self.export_mode == "AnkiDeck":
            export.gen_anki(self.interface, results, self.output)
        elif self.export_mode == "Update":
            deck_name = self.output[0]
            model_name = self.output[1]
            export.update_anki(self.interface, results, self.col, deck_name, model_name)
        return 0


if __name__ == "__main__":
    root = Tk()
    root.geometry("720x600")
    root.minsize(650, 500)
    # root.state("zoomed")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.title("AnkiChinese")

    controller = Controller(root)
    controller.show_page("MainMenu")

    root.mainloop()
