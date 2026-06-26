# acercontrol/gui_boot.py
"""Boot service controls for the Phase 6 main page."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from acercontrol.privilege import run_privileged
from acercontrol.profiles import PROFILES, Profile
from acercontrol.systemd import (
    boot_instance_for_profile,
    read_boot_profile,
    service_active,
    service_enabled,
)


PROFILE_CHOICES = ("eco", "quiet", "balanced", "performance", "turbo")
SERVICE_NAME = "acer-performance.service"


class BootServicePanel(Adw.PreferencesGroup):
    """Controls for boot-time profile persistence."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._updating = False

        self.set_title("BOOT SERVICE")
        self.set_description("Apply a profile during startup and after resume.")

        self._service_row = Adw.ActionRow(title=SERVICE_NAME)
        self._service_status = Gtk.Label(xalign=1.0)
        self._service_status.add_css_class("dim-label")
        self._service_status.set_valign(Gtk.Align.CENTER)
        self._service_row.add_suffix(self._service_status)
        self.add(self._service_row)

        self._enable_row = Adw.ActionRow(title="Enable at boot")
        self._enable_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._enable_switch.connect("notify::active", self._on_enable_switch_changed)
        self._enable_row.add_suffix(self._enable_switch)
        self._enable_row.set_activatable_widget(self._enable_switch)
        self.add(self._enable_row)

        self._profile_model = Gtk.StringList.new(PROFILE_CHOICES)
        self._profile_row = Adw.ComboRow(title="Boot profile")
        self._profile_row.set_model(self._profile_model)
        self._profile_row.connect("notify::selected", self._on_profile_selected)
        self.add(self._profile_row)

        self._apply_row = Adw.ActionRow(title="Apply now")
        self._apply_button = Gtk.Button(label="Apply now")
        self._apply_button.add_css_class("suggested-action")
        self._apply_button.set_valign(Gtk.Align.CENTER)
        self._apply_button.connect("clicked", self._on_apply_now_clicked)
        self._apply_row.add_suffix(self._apply_button)
        self._apply_row.set_activatable_widget(self._apply_button)
        self.add(self._apply_row)

        self.refresh()

    def refresh(self) -> None:
        enabled = service_enabled(SERVICE_NAME)
        active = service_active(SERVICE_NAME)
        boot_profile = read_boot_profile()

        selected_name = self._profile_name(boot_profile)
        try:
            selected_index = PROFILE_CHOICES.index(selected_name)
        except ValueError:
            selected_index = PROFILE_CHOICES.index("balanced")

        self._updating = True
        try:
            self._profile_row.set_selected(selected_index)
            self._enable_switch.set_active(enabled == "enabled")
        finally:
            self._updating = False

        installed = enabled != "not-found"
        self._enable_switch.set_sensitive(installed)
        self._profile_row.set_sensitive(installed)
        self._apply_button.set_sensitive(installed)
        self._service_status.set_text(self._format_service_status(enabled, active))

    def _profile_name(self, profile: Profile) -> str:
        if profile is Profile.CUSTOM:
            return "balanced"
        return profile.display

    def _format_service_status(self, enabled: str, active: str) -> str:
        if enabled == "not-found":
            return "not installed"
        if active in {"active", "activating", "failed"}:
            return f"{enabled}, {active}"
        return enabled

    def _selected_profile_name(self) -> str:
        selected = self._profile_row.get_selected()
        if selected >= len(PROFILE_CHOICES):
            return "balanced"
        return PROFILE_CHOICES[selected]

    def _on_enable_switch_changed(self, switch: Gtk.Switch, _pspec) -> None:
        if self._updating:
            return
        action = "enable" if switch.get_active() else "disable"
        success_message = "Boot service enabled" if action == "enable" else "Boot service disabled"
        result = run_privileged(["acercontrol-manage-service", action, SERVICE_NAME])
        self._finish_mutation(result, success_message)

    def _on_profile_selected(self, _row: Adw.ComboRow, _pspec) -> None:
        if self._updating:
            return
        self._apply_boot_profile(self._selected_profile_name())

    def _on_apply_now_clicked(self, _button: Gtk.Button) -> None:
        self._apply_boot_profile(self._selected_profile_name())

    def _apply_boot_profile(self, profile_name: str) -> None:
        set_result = run_privileged(["acercontrol-set-boot-profile", PROFILES[profile_name]])
        if set_result.cancelled or set_result.returncode != 0:
            self._finish_mutation(set_result, "Boot profile updated")
            return

        start_result = run_privileged(
            ["acercontrol-manage-service", "start", boot_instance_for_profile(profile_name)]
        )
        self._finish_mutation(start_result, "Boot profile updated")

    def _finish_mutation(self, result, success_message: str) -> None:
        self.refresh()
        if result.cancelled:
            self._toast("Authorization cancelled")
            return
        if result.returncode != 0:
            self._toast("Boot service update failed. See terminal for details.")
            return
        self._toast(success_message)

    def _toast(self, message: str) -> None:
        if hasattr(self._window, "show_toast"):
            self._window.show_toast(message)
