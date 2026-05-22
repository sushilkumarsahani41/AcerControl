# acercontrol/tray_status.py
"""StatusNotifierWatcher availability checks for the optional tray helper."""

from __future__ import annotations


WATCHER_BUS_NAME = "org.kde.StatusNotifierWatcher"


def _load_gio():
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib  # noqa: PLC0415
    except (ImportError, ValueError, AttributeError, TypeError) as exc:
        return None, None, f"{type(exc).__name__}: {exc}"
    return Gio, GLib, ""


def tray_status() -> str:
    """Return a stable tray availability status string."""
    return tray_status_detail()["status"]


def tray_status_detail() -> dict[str, str]:
    """Return session tray availability details without raising."""
    Gio, GLib, load_error = _load_gio()
    if Gio is None or GLib is None:
        return {
            "status": "unknown",
            "watcher": WATCHER_BUS_NAME,
            "detail": load_error or "Gio unavailable",
        }

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", (WATCHER_BUS_NAME,)),
            GLib.VariantType("(b)"),
            Gio.DBusCallFlags.NONE,
            1000,
            None,
        )
        available = bool(result.unpack()[0])
    except GLib.Error as exc:
        return {
            "status": "no-session-bus",
            "watcher": WATCHER_BUS_NAME,
            "detail": str(exc),
        }
    except (AttributeError, TypeError, ValueError) as exc:
        return {
            "status": "unknown",
            "watcher": WATCHER_BUS_NAME,
            "detail": f"{type(exc).__name__}: {exc}",
        }

    return {
        "status": "available" if available else "missing-watcher",
        "watcher": WATCHER_BUS_NAME,
        "detail": "StatusNotifierWatcher owner present" if available else "StatusNotifierWatcher missing",
    }


__all__ = ["WATCHER_BUS_NAME", "tray_status", "tray_status_detail"]
