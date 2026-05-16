# acercontrol/gui_status_pages.py — Phase 3
"""StatusPage factory functions — one per blocker probe key (GUI-03).

Each factory takes a `window` argument (MainWindow instance) so the
button callbacks can dispatch into the window's signal handlers
(_on_reload_acer_wmi_clicked, _route).

All copy strings are VERBATIM from 03-UI-SPEC.md § StatusPage Copy Table.
Do not paraphrase — the checker greps for these strings.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from acercontrol.features import probe


def _make_action_box(primary_button: Gtk.Button | None, window) -> Gtk.Box:
    """Vertical box: primary CTA (when present) + Refresh footer button."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_halign(Gtk.Align.CENTER)
    if primary_button is not None:
        box.append(primary_button)
    refresh = Gtk.Button(label="Refresh")
    refresh.add_css_class("flat")
    refresh.connect("clicked", lambda *_: window._route(probe()))
    box.append(refresh)
    return box


def acer_wmi_not_loaded(window) -> Adw.StatusPage:
    page = Adw.StatusPage()
    page.set_icon_name("dialog-error-symbolic")
    page.set_title("acer_wmi module not loaded")
    page.set_description(
        "The acer_wmi kernel module is required for performance control. "
        "Click below to load it with predator_v4=1."
    )
    btn = Gtk.Button(label="Load module")
    btn.add_css_class("suggested-action")
    btn.add_css_class("pill")
    btn.connect("clicked", window._on_reload_acer_wmi_clicked)
    page.set_child(_make_action_box(btn, window))
    return page


def predator_v4_disabled(window) -> Adw.StatusPage:
    page = Adw.StatusPage()
    page.set_icon_name("dialog-warning-symbolic")
    page.set_title("Predator mode disabled")
    page.set_description(
        "acer_wmi is loaded without predator_v4=1. Performance, turbo, "
        "and LED features are unavailable until the module is reloaded."
    )
    btn = Gtk.Button(label="Reload with predator_v4=1")
    btn.add_css_class("suggested-action")
    btn.add_css_class("pill")
    btn.connect("clicked", window._on_reload_acer_wmi_clicked)
    page.set_child(_make_action_box(btn, window))
    return page


def platform_profile_missing(window) -> Adw.StatusPage:
    page = Adw.StatusPage()
    page.set_icon_name("dialog-error-symbolic")
    page.set_title("platform_profile interface unavailable")
    page.set_description(
        "/sys/firmware/acpi/platform_profile does not exist. This usually "
        "means the kernel is older than 5.12 or ACPI is missing the "
        "platform_profile object. No userspace fix is possible."
    )
    # Read-only — Refresh only, no remediation button
    page.set_child(_make_action_box(None, window))
    return page


def no_acer_hwmon(window) -> Adw.StatusPage:
    page = Adw.StatusPage()
    page.set_icon_name("dialog-error-symbolic")
    page.set_title("Acer sensors unavailable")
    page.set_description(
        "No hwmon device named “acer” was found. Fan and "
        "temperature monitoring will not work. Confirm acer_wmi is "
        "loaded with predator_v4=1."
    )
    page.set_child(_make_action_box(None, window))
    return page


def placeholder_ok(window) -> Adw.StatusPage:
    """Empty-state placeholder shown when probe().ok is True. Removed in Phase 4."""
    page = Adw.StatusPage()
    page.set_icon_name("applications-system-symbolic")
    page.set_title("Profile controls coming in Phase 4")
    page.set_description(
        "Hardware checks passed. The main controls are not implemented in this phase."
    )
    return page


# Dispatch table: probe check name → factory. _route in gui_window.py keys on this.
BLOCKER_FACTORIES = {
    "acer_wmi module loaded": acer_wmi_not_loaded,
    "predator_v4 mode": predator_v4_disabled,
    "platform_profile sysfs": platform_profile_missing,
    "acer hwmon (fan+temp)": no_acer_hwmon,
}
