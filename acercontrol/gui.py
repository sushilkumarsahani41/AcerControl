# acercontrol/gui.py — Phase 3
"""AcerControl GUI entry point (GUI-01, GUI-02).

Single-instance Adw.Application registered as org.acercontrol.AcerControl.
Second launch fires `activate` on the primary instance — do_activate
focuses the existing window via self.props.active_window.

Wired from pyproject.toml [project.scripts]:
    acercontrol-gui = "acercontrol.gui:main"
"""
from __future__ import annotations

import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from acercontrol.gui_window import MainWindow
from acercontrol.gui_theme import apply_predator_theme


class AcerControlApp(Adw.Application):

    def __init__(self) -> None:
        super().__init__(
            application_id="org.acercontrol.AcerControl",
            # DEFAULT_FLAGS — NOT FLAGS_NONE (deprecated since GLib 2.74).
            # Phase 5 Gio.Notification will require the .desktop basename
            # to match this application_id (set in Phase 8).
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:
        # GUI-02: second launch fires activate on the primary instance.
        # Focus existing window if one exists; otherwise construct.
        apply_predator_theme(self)
        win = self.props.active_window
        if win is None:
            win = MainWindow(application=self)
        win.present()


def main() -> int:
    """Entry point wired from pyproject.toml [project.scripts]."""
    return AcerControlApp().run(None)


if __name__ == "__main__":
    sys.exit(main())
