"""Headless GUI smoke test using a stubbed tkinter module."""

from __future__ import annotations

import sys
from types import ModuleType

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
    ttk_module = ModuleType("tkinter.ttk")
    setattr(ttk_module, "Notebook", _DummyNotebook)
    setattr(ttk_module, "Frame", _DummyWidget)
    setattr(ttk_module, "Label", _DummyWidget)
    setattr(ttk_module, "Entry", _DummyWidget)
    setattr(ttk_module, "Combobox", _DummyWidget)
    setattr(ttk_module, "Checkbutton", _DummyWidget)
    setattr(ttk_module, "Button", _DummyButton)

    messagebox = ModuleType("tkinter.messagebox")
    setattr(messagebox, "showerror", lambda *_: None)

    filedialog = ModuleType("tkinter.filedialog")
    setattr(filedialog, "askopenfilename", lambda **_kwargs: "")
    setattr(filedialog, "askopenfilenames", lambda **_kwargs: ())
    setattr(filedialog, "askdirectory", lambda **_kwargs: "")
    setattr(filedialog, "asksaveasfilename", lambda **_kwargs: "")

    tk_module = ModuleType("tkinter")
    setattr(tk_module, "Tk", _DummyTk)
    setattr(tk_module, "StringVar", _DummyVar)
    setattr(tk_module, "BooleanVar", _DummyVar)
    setattr(tk_module, "Text", _DummyWidget)
    setattr(tk_module, "ttk", ttk_module)
    setattr(tk_module, "messagebox", messagebox)
    setattr(tk_module, "filedialog", filedialog)
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
