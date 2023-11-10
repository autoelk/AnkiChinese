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

        # BASIC OPTIONS SECTION
        self.create_basic_opt()

        # ADVANCED OPTIONS SECTION
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

    # validation helpers
    def val_chars(self):
        content = self.char_text_box.get(1.0, "end-1c")
        valid = len(content) > 0
        self.chars_error_msg.set("" if valid else "Include at least one character")
        self.chars_valid = valid
        self.update_next_btn_state()
        return valid

    def val_output(self, new_val):
        valid = (
            regex.search(r"[^\/]+(?=\." + regex.escape(self.ext) + r"$)", new_val)
            is not None
        )
        self.output_error_msg.set("" if valid else "Invalid file location")
        self.output_valid = valid
        self.update_next_btn_state()
        return valid

    # enable next button if and only if all input fields are valid
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
        controller.chars = self.char_text_box.get("1.0", "end")
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

    def create_basic_opt(self):
        basic_opt_frame = ttk.Frame(self)
        basic_opt_frame.grid(row=1, column=0)

        # Characters to scrape
        char_frame = ttk.Frame(basic_opt_frame)
        char_frame.grid(row=0, column=1)

        ttk.Label(char_frame, text="Characters").grid(row=0, column=0, padx=5, sticky=W)
        self.char_text_box = Text(char_frame, width=30, height=12)
        self.char_text_box.grid(row=1, column=0)
        self.char_text_box.bind("<Leave>", lambda e: self.val_chars())
        self.chars_valid = False
        self.chars_error_msg = StringVar(self)
        ttk.Label(
            char_frame,
            font="TkSmallCaptionFont",
            foreground="red",
            textvariable=self.chars_error_msg,
        ).grid(row=3, column=0, sticky=W)
        ttk.Button(char_frame, text="Import", command=self.import_chars).grid(
            row=2, column=0, padx=5, sticky=EW
        )
        self.update_existing = IntVar()
        ttk.Checkbutton(
            basic_opt_frame,
            text="Include existing characters",
            variable=self.update_existing,
            onvalue=1,
            offvalue=0,
        ).grid(row=1, column=0, columnspan=3)
        self.update_existing.set(0)

        # Deck and Model
        deck_model_frame = ttk.Frame(basic_opt_frame)
        deck_model_frame.grid(row=0, column=0)

        ttk.Label(deck_model_frame, text="Select deck & model").grid(
            row=0, column=0, padx=5, sticky=W
        )
        self.deck_tree = ttk.Treeview(deck_model_frame, selectmode=BROWSE, show="tree")
        self.deck_tree.grid(row=1, column=0, padx=5)

        ttk.Label(deck_model_frame, text="Fields").grid(
            row=0, column=1, padx=5, sticky=W
        )
        self.model_tree = ttk.Treeview(deck_model_frame, selectmode=BROWSE, show="tree")
        self.model_tree.grid(row=1, column=1, padx=5)

        self.controller.col = Collection()
        self.deck_names = self.controller.col.cards.list_decks()
        self.model_names = {}
        self.column_names = {}

        cards_in_deck = {}
        notes_in_deck = {}
        for deck_name in self.deck_names:
            cards = self.controller.col.cards.merge_notes()
            cards_in_deck[deck_name] = cards[cards["cdeck"].str.startswith(deck_name)]
            notes_in_deck[deck_name] = self.controller.col.notes[
                self.controller.col.notes.nid.isin(cards_in_deck[deck_name].nid)
            ]
            self.model_names[deck_name] = notes_in_deck[deck_name].list_models()

            self.deck_tree.insert("", "end", deck_name, text=deck_name)
            for model_name in self.model_names[deck_name]:
                model_id = deck_name + "::" + model_name

                self.deck_tree.insert(deck_name, "end", model_id, text=model_name)
                self.column_names[model_id] = (
                    notes_in_deck[deck_name]
                    .copy()
                    .query(f"nmodel == '{model_name}'")
                    .fields_as_columns()
                    .filter(regex="^nfld_", axis="columns")
                    .columns.str.replace("nfld_", "")
                )

                for column_name in self.column_names[model_id]:
                    self.model_tree.insert(
                        "",
                        "end",
                        model_id + "::" + column_name,
                        text=column_name,
                        tags=("hanzi" if column_name == "Hanzi" else ""),
                    )
                    self.model_tree.detach(model_id + "::" + column_name)
            self.deck_tree.item(deck_name, open=TRUE)

        # Error messages
        self.model_tree.insert(
            "",
            "end",
            "deck_not_model",
            text="Please select a model",
            tags="error",
        )
        self.model_tree.detach("deck_not_model")
        self.model_tree.insert(
            "",
            "end",
            "no_hanzi",
            text='Model must contain "Hanzi"',
            tags="error",
        )
        self.model_tree.detach("no_hanzi")

        self.model_tree.tag_configure("hanzi", foreground="green")
        self.model_tree.tag_configure("error", foreground="red")
        self.output_valid = False
        self.deck_tree.bind(
            "<<TreeviewSelect>>",
            lambda e: self.do_select_model(),
        )

    def show_model_cols(self, model_id):
        # error messages
        if model_id not in self.column_names:
            self.model_tree.move("deck_not_model", "", "end")
        else:
            self.model_tree.detach("deck_not_model")
            if "Hanzi" not in self.column_names[model_id]:
                self.model_tree.move("no_hanzi", "", "end")
            else:
                self.model_tree.detach("no_hanzi")

        for deck_name in self.deck_names:
            for model_name in self.model_names[deck_name]:
                curr_model_id = deck_name + "::" + model_name
                for column_name in self.column_names[curr_model_id]:
                    if curr_model_id == model_id:
                        self.model_tree.move(
                            curr_model_id + "::" + column_name, "", "end"
                        )
                    else:
                        self.model_tree.detach(curr_model_id + "::" + column_name)

    def do_select_model(self):
        self.show_model_cols(self.deck_tree.selection()[0])
        self.val_output(self.deck_tree.selection()[0])

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
        controller.chars = self.char_text_box.get("1.0", "end")
        controller.req_simul = int(self.max_req_simul.value.get())
        controller.req_ps = int(self.max_req_ps.value.get())
        controller.num_ex = int(self.num_ex.value.get())
        controller.num_defs = int(self.num_defs.value.get())
        controller.output = self.deck_tree.selection()[0].split("::", 2)
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
        self.log_text_box = Text(main_frame)
        self.log_text_box.grid(row=1, column=0, padx=5, sticky=NSEW)
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
    def __init__(self, pbar):
        self.pbar = pbar

    def config_pbar(self, num):
        self.pbar.configure(maximum=num)

    def start_pbar(self):
        self.pbar.event_generate("<<StartProgressBar>>")

    async def step_pbar(self):
        self.pbar.event_generate("<<StepProgressBar>>")

    def finish_pbar(self):
        self.pbar.event_generate("<<FinishProgressBar>>")

    def print(self, str):
        print(str)


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

        self.interface = GUI(self.get_page("Generator").progress_bar)

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
        self.chars = list(
            filter(lambda char: "\u4e00" <= char <= "\u9fff", set(self.chars))
        )

        self.interface.config_pbar(len(self.chars))
        results = await scraper.main(
            self.chars,
            self.req_simul,
            self.req_ps,
            self.num_ex,
            self.num_defs,
            self.interface,
        )
        if self.export_mode == "CSV":
            export.gen_csv(results, self.output)
        elif self.export_mode == "AnkiDeck":
            export.gen_anki(results, self.output)
        elif self.export_mode == "Update":
            deck_name = self.output[0]
            model_name = self.output[1]
            res, notes_added_nids = export.update_anki(
                results, self.col, deck_name, model_name
            )
            export.update_anki_apply_changes(self.col, res, notes_added_nids, deck_name)


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
