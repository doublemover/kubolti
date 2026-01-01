"""Headless GUI smoke test using a stubbed tkinter module."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from dem2dsf import gui


class _DummyWidget:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def grid(self, *args, **kwargs) -> None:
        return None

    def pack(self, *args, **kwargs) -> None:
        return None

    def columnconfigure(self, *args, **kwargs) -> None:
        return None

    def insert(self, *args, **kwargs) -> None:
        return None

    def see(self, *args, **kwargs) -> None:
        return None


class _DummyVar:
    def __init__(self, value=None) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


class _DummyTk(_DummyWidget):
    def title(self, *args, **kwargs) -> None:
        return None

    def mainloop(self) -> None:
        return None

    def destroy(self) -> None:
        return None

    def protocol(self, *_args, **_kwargs) -> None:
        return None


class _DummyNotebook(_DummyWidget):
    def add(self, *args, **kwargs) -> None:
        return None


class _DummyButton(_DummyWidget):
    def __init__(self, *args, **kwargs) -> None:
        self.command = kwargs.get("command")


def _install_stub_tkinter() -> None:
    ttk_module = SimpleNamespace(
        Notebook=_DummyNotebook,
        Frame=_DummyWidget,
        Label=_DummyWidget,
        Entry=_DummyWidget,
        Combobox=_DummyWidget,
        Checkbutton=_DummyWidget,
        Button=_DummyButton,
    )
    messagebox = SimpleNamespace(showerror=lambda *_: None)
    filedialog = SimpleNamespace(
        askopenfilename=lambda **_kwargs: "",
        askopenfilenames=lambda **_kwargs: (),
        askdirectory=lambda **_kwargs: "",
        asksaveasfilename=lambda **_kwargs: "",
    )
    tk_module = SimpleNamespace(
        Tk=_DummyTk,
        StringVar=_DummyVar,
        BooleanVar=_DummyVar,
        Text=_DummyWidget,
        ttk=ttk_module,
        messagebox=messagebox,
        filedialog=filedialog,
    )
    sys.modules.setdefault("tkinter", tk_module)
    sys.modules.setdefault("tkinter.ttk", ttk_module)
    sys.modules.setdefault("tkinter.messagebox", messagebox)
    sys.modules.setdefault("tkinter.filedialog", filedialog)


def main() -> int:
    """Run a headless GUI smoke test."""
    _install_stub_tkinter()
    gui.launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
