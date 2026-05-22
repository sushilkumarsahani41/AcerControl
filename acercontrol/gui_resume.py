# acercontrol/gui_resume.py
"""Suspend/resume profile restoration controller."""

from __future__ import annotations

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


class ResumeReapplyController:
    """Subscribe to login1 resume signals and delegate restoration to MainWindow."""

    def __init__(self, window) -> None:
        self._window = window
        self._connection = None
        self._subscription_id: int | None = None

    def start(self) -> None:
        if self._subscription_id is not None:
            return
        try:
            self._connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self._subscription_id = self._connection.signal_subscribe(
                "org.freedesktop.login1",
                "org.freedesktop.login1.Manager",
                "PrepareForSleep",
                "/org/freedesktop/login1",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_prepare_for_sleep,
                None,
            )
        except (GLib.Error, AttributeError, TypeError):
            self._connection = None
            self._subscription_id = None

    def stop(self) -> None:
        if self._connection is not None and self._subscription_id is not None:
            try:
                self._connection.signal_unsubscribe(self._subscription_id)
            except (GLib.Error, AttributeError, TypeError):
                pass
        self._subscription_id = None
        self._connection = None

    def _on_prepare_for_sleep(
        self,
        _connection,
        _sender_name,
        _object_path,
        _interface_name,
        _signal_name,
        parameters,
        _user_data,
    ) -> None:
        try:
            start = bool(parameters.unpack()[0])
        except (AttributeError, IndexError, TypeError):
            return
        if start:
            return
        self._window.reapply_last_profile_after_resume()
