# acercontrol/gui_profiles.py
"""Profile control panel for the Phase 4 core value loop."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from acercontrol.core import list_available_profiles, read_profile
from acercontrol.privilege import run_privileged
from acercontrol.profiles import PROFILES, Profile


ORDER = ("eco", "quiet", "balanced", "performance", "turbo")


class ProfileControlPanel(Adw.PreferencesGroup):
    """Read-back-driven profile controls.

    The requested click never becomes visual truth. Active styling moves only
    after read_profile() reports the actual platform profile.
    """

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._buttons: dict[str, Gtk.Button] = {}
        self._active_profile = Profile.CUSTOM
        self._pending = False
        self._pending_requested: str | None = None
        self._previous_profile = Profile.CUSTOM
        self._readback_source_id: int | None = None

        self.set_title("Performance Profile")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        self._status_label = Gtk.Label(xalign=0.0)
        self._status_label.add_css_class("heading")
        content.append(self._status_label)

        self._helper_label = Gtk.Label(xalign=0.0)
        self._helper_label.set_wrap(True)
        self._helper_label.add_css_class("dim-label")
        content.append(self._helper_label)

        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_column_spacing(8)
        self._flow.set_row_spacing(8)
        self._flow.set_min_children_per_line(1)
        self._flow.set_max_children_per_line(5)
        content.append(self._flow)

        self._pending_label = Gtk.Label(xalign=0.0)
        self._pending_label.add_css_class("dim-label")
        self._pending_label.set_visible(False)
        content.append(self._pending_label)

        for profile_name in ORDER:
            button = Gtk.Button(label=profile_name)
            button.add_css_class("pill")
            button.set_size_request(128, 56)
            button.set_tooltip_text(f"Set profile to {profile_name}")
            self._set_accessible_label(button, f"Set profile to {profile_name}")
            button.connect("clicked", self._on_profile_clicked, profile_name)
            self._buttons[profile_name] = button
            self._flow.append(button)

        self.add(content)

        self.refresh(initial_focus=True)

    def refresh(self, *, initial_focus: bool = False) -> None:
        actual = read_profile()
        self._render_profile_state(actual)
        if initial_focus:
            self._focus_initial()

    def _set_accessible_label(self, button: Gtk.Button, text: str) -> None:
        try:
            button.update_property(Gtk.AccessibleProperty.LABEL, text, -1)
        except (AttributeError, TypeError, ValueError):
            try:
                button.update_property([Gtk.AccessibleProperty.LABEL], [text])
            except (AttributeError, TypeError, ValueError):
                button.set_tooltip_text(text)

    def _profile_name(self, profile: Profile) -> str | None:
        if profile is Profile.CUSTOM:
            return None
        return profile.display

    def _available_names(self) -> set[str] | None:
        available = list_available_profiles()
        if not available:
            return None
        names = {self._profile_name(profile) for profile in available}
        return {name for name in names if name is not None}

    def _render_profile_state(self, actual: Profile) -> None:
        self._active_profile = actual
        active_name = self._profile_name(actual)
        available_names = self._available_names()

        if actual is Profile.CUSTOM:
            self._status_label.set_text("Current profile: Custom")
            self._helper_label.set_text("Click a profile to set a known Acer profile.")
            self._helper_label.set_visible(True)
        else:
            self._status_label.set_text(f"Current profile: {actual.display}")
            self._helper_label.set_text("")
            self._helper_label.set_visible(False)

        for name, button in self._buttons.items():
            is_active = name == active_name
            if is_active:
                button.add_css_class("suggested-action")
            else:
                button.remove_css_class("suggested-action")

            accessible = f"Set profile to {name}"
            if is_active:
                accessible = f"{accessible}. Current profile"
            self._set_accessible_label(button, accessible)

            if self._pending:
                button.set_sensitive(False)
                continue

            is_available = available_names is None or name in available_names
            button.set_sensitive(is_available)
            if is_available:
                button.set_tooltip_text(f"Set profile to {name}")
            else:
                button.set_tooltip_text("Unavailable on this hardware")

    def _on_profile_clicked(self, _button: Gtk.Button, requested_profile: str) -> None:
        if self._pending:
            return
        active_name = self._profile_name(self._active_profile)
        if active_name == requested_profile:
            return

        self._previous_profile = self._active_profile
        self._pending_requested = requested_profile
        self._pending = True
        self._pending_label.set_text("Awaiting authorisation...")
        self._pending_label.set_visible(True)
        self._render_profile_state(self._active_profile)

        result = run_privileged(["acercontrol-setprofile", PROFILES[requested_profile]])
        if result.cancelled:
            self._finish_cancelled(requested_profile)
            return
        if result.returncode != 0:
            self._finish_failed()
            return

        self._readback_source_id = GLib.timeout_add(250, self._verify_readback, requested_profile)

    def _finish_cancelled(self, requested_profile: str) -> None:
        previous = self._previous_profile
        self._clear_pending()
        self._render_profile_state(previous)
        if previous is Profile.CUSTOM:
            self._focus_name(requested_profile)
        else:
            self._focus_profile(previous)
        self._toast("Authorization cancelled", timeout=3)

    def _finish_failed(self) -> None:
        self._clear_pending()
        actual = read_profile()
        self._render_profile_state(actual)
        self._focus_profile(actual)
        self._toast("Profile change failed. See terminal for details.")

    def _verify_readback(self, requested_profile: str):
        actual = read_profile()
        requested_value = PROFILES[requested_profile]
        self._clear_pending()
        self._render_profile_state(actual)

        if actual.value == requested_value:
            self._focus_name(requested_profile)
            if hasattr(self._window, "notify_profile_change"):
                self._window.notify_profile_change(requested_profile)
            else:
                self._toast(f"Switched to {requested_profile}")
        else:
            self._focus_profile(actual)
            self._toast(
                "Profile not applied — power-profiles-daemon may be overriding writes"
            )
            self._window.show_ppd_banner(force=True)

        self._readback_source_id = None
        return GLib.SOURCE_REMOVE

    def _clear_pending(self) -> None:
        self._pending = False
        self._pending_requested = None
        self._pending_label.set_text("")
        self._pending_label.set_visible(False)

    def _toast(self, message: str, *, timeout: int | None = None) -> None:
        if hasattr(self._window, "show_toast"):
            self._window.show_toast(message, timeout=timeout)
        elif timeout is None:
            self._window._toast(message)
        else:
            self._window._toast(message)

    def _focus_initial(self):
        self._focus_profile(self._active_profile)
        return GLib.SOURCE_REMOVE

    def _focus_profile(self, profile: Profile) -> None:
        name = self._profile_name(profile)
        if name is None:
            name = "balanced"
        self._focus_name(name)

    def _focus_name(self, name: str) -> None:
        button = self._buttons.get(name)
        if button is not None and button.get_sensitive():
            button.grab_focus()
