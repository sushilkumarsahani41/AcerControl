# acercontrol/gui_notifications.py
"""Focus-aware notification routing for the GTK application."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio  # noqa: E402


PROFILE_NOTIFICATION_ID = "profile-change"
CRITICAL_NOTIFICATION_ID = "critical-temp"
CRITICAL_NORMAL_NOTIFICATION_ID = "critical-temp-normal"
CRITICAL_ENTER_C = 90
CRITICAL_EXIT_C = 85


class ProfileChangeNotifier:
    """Route profile changes to a toast or one stable desktop notification."""

    def __init__(self, window) -> None:
        self._window = window

    def notify(self, profile_name: str) -> None:
        if self._window.is_focused():
            self._window.show_toast(f"Switched to {profile_name}")
            return

        notification = Gio.Notification.new("Profile changed")
        notification.set_body(f"AcerControl is now using {profile_name}.")
        app = self._window.get_application()
        if app is not None:
            app.send_notification("profile-change", notification)


class CriticalTempNotifier:
    """Notify only when CPU package temperature crosses critical thresholds."""

    def __init__(self, window) -> None:
        self._window = window
        self._critical_active = False

    def update(self, cpu_package_c: float | None) -> None:
        if cpu_package_c is None:
            return

        if not self._critical_active:
            if cpu_package_c >= CRITICAL_ENTER_C:
                self._critical_active = True
                self._notify_critical()
            return

        if cpu_package_c < CRITICAL_EXIT_C:
            self._critical_active = False
            self._notify_normal()

    def _notify_critical(self) -> None:
        if self._window.is_focused():
            self._window.show_toast("CPU temperature critical")
            return

        notification = Gio.Notification.new("CPU temperature critical")
        notification.set_body("CPU package temperature is above 90 C.")
        app = self._window.get_application()
        if app is not None:
            app.send_notification("critical-temp", notification)

    def _notify_normal(self) -> None:
        if self._window.is_focused():
            self._window.show_toast("CPU temperature back to normal")
            return

        notification = Gio.Notification.new("CPU temperature back to normal")
        notification.set_body("CPU package temperature is below 85 C.")
        app = self._window.get_application()
        if app is not None:
            app.send_notification("critical-temp-normal", notification)
