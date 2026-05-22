# acercontrol/tray.py
"""Optional GTK3/Ayatana tray helper for AcerControl."""

from __future__ import annotations

import shutil
import subprocess
import sys

from acercontrol.core import PROFILES, Profile, list_available_profiles, read_profile
from acercontrol.privilege import run_privileged
from acercontrol.tray_status import tray_status


PROFILE_ORDER = ("eco", "quiet", "balanced", "performance", "turbo")
APP_ID = "org.acercontrol.AcerControl"
INDICATOR_ID = "acercontrol-tray"


def _load_tray_stack():
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import GLib, Gtk  # noqa: PLC0415
        from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: PLC0415
    except (ImportError, ValueError, AttributeError) as exc:
        print(f"AcerControl tray unavailable: optional tray libraries missing ({exc})")
        return None
    return GLib, Gtk, AppIndicator


def _profile_name(profile: Profile) -> str | None:
    if profile is Profile.CUSTOM:
        return None
    return profile.display


class TrayApp:
    def __init__(self, GLib, Gtk, AppIndicator) -> None:
        self.GLib = GLib
        self.Gtk = Gtk
        self.AppIndicator = AppIndicator
        self.profile_items = {}
        self._refreshing = False
        self._source_id = None

        self.indicator = AppIndicator.Indicator.new(
            INDICATOR_ID,
            APP_ID,
            AppIndicator.IndicatorCategory.SYSTEM_SERVICES,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self._build_menu())

    def _build_menu(self):
        Gtk = self.Gtk
        menu = Gtk.Menu()

        for profile_name in PROFILE_ORDER:
            item = Gtk.CheckMenuItem.new_with_label(profile_name)
            item.set_draw_as_radio(True)
            item.connect("activate", self._on_profile_activate, profile_name)
            self.profile_items[profile_name] = item
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

        show_item = Gtk.MenuItem.new_with_label("Show AcerControl")
        show_item.connect("activate", self._on_show_activate)
        menu.append(show_item)

        quit_item = Gtk.MenuItem.new_with_label("Quit")
        quit_item.connect("activate", self._on_quit_activate)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_profile_activate(self, _item, profile_name: str) -> None:
        if self._refreshing:
            return
        result = run_privileged(["acercontrol-setprofile", PROFILES[profile_name]])
        if result.cancelled:
            print("AcerControl tray: profile change cancelled")
        elif result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            if detail:
                print(f"AcerControl tray: profile change failed: {detail}")
            else:
                print("AcerControl tray: profile change failed")
        self.refresh()

    def _on_show_activate(self, _item) -> None:
        executable = shutil.which("acercontrol-gui")
        argv = [executable] if executable else [sys.executable, "-m", "acercontrol.gui"]
        try:
            subprocess.Popen(argv)
        except OSError as exc:
            print(f"AcerControl tray: unable to launch GUI: {exc}")

    def _on_quit_activate(self, _item) -> None:
        self.Gtk.main_quit()

    def refresh(self) -> bool:
        current_name = _profile_name(read_profile())
        available = list_available_profiles()
        available_names = {_profile_name(profile) for profile in available}
        known_choices = bool(available_names)

        self._refreshing = True
        try:
            for profile_name, item in self.profile_items.items():
                item.set_active(profile_name == current_name)
                item.set_sensitive(not known_choices or profile_name in available_names)
            if current_name and hasattr(self.indicator, "set_label"):
                self.indicator.set_label(current_name, "")
        finally:
            self._refreshing = False

        return True

    def run(self) -> int:
        self.refresh()
        self._source_id = self.GLib.timeout_add_seconds(2, self.refresh)
        self.Gtk.main()
        if self._source_id is not None:
            self.GLib.source_remove(self._source_id)
            self._source_id = None
        return 0


def main() -> int:
    status = tray_status()
    if status != "available":
        print(f"AcerControl tray unavailable: {status}")
        return 0

    stack = _load_tray_stack()
    if stack is None:
        return 0

    GLib, Gtk, AppIndicator = stack
    return TrayApp(GLib, Gtk, AppIndicator).run()


if __name__ == "__main__":
    raise SystemExit(main())
