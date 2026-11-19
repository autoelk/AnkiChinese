from contextlib import contextmanager


class Interface:
    @contextmanager
    def progress(self, label, total, unit):
        if total:
            self.print(f"{label}...")
        yield lambda count: None

    def print(self, str: str):
        pass

    def confirm(self, msg: str):
        pass

    def start_pbar(self):
        pass

    def step_pbar(self):
        pass

    def finish_pbar(self):
        pass
