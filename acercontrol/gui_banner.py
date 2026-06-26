# acercontrol/gui_banner.py — Phase 3
"""Warning banners + PPD Learn-more explainer dialog (GUI-04).

Landmine #1 fallback (locked path): banner titles are PLAIN TEXT. No
Pango <a href> link markup; Adw.Banner does not propagate activate-link.
The 'About power-profiles-daemon' affordance lives in the MainWindow's
HeaderBar primary menu, not on the banner.

All copy strings are VERBATIM from 03-UI-SPEC.md § Banner copy and
§ Learn-more Dialog.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402


def build_ppd_banner(window) -> Adw.Banner:
    """PPD-active banner (warning). Single button: Disable PPD. NO Pango
    link in title (Landmine #1)."""
    banner = Adw.Banner.new(
        "power-profiles-daemon is running and will overwrite profile changes"
    )
    banner.set_button_label("Disable PPD")
    banner.set_revealed(True)
    banner.connect("button-clicked", window._on_disable_ppd_clicked)
    banner.add_css_class("warning")
    return banner


def build_blacklist_banner() -> Adw.Banner:
    """acer_wmi blacklist detected (warning, read-only). No button."""
    banner = Adw.Banner.new(
        "acer_wmi is blacklisted in /etc/modprobe.d. "
        "The module will not load on next boot."
    )
    banner.set_revealed(True)
    banner.add_css_class("warning")
    return banner


def build_coretemp_banner() -> Adw.Banner:
    """coretemp hwmon missing (warning, read-only). No button."""
    banner = Adw.Banner.new(
        "CPU package temperature unavailable: coretemp module not loaded."
    )
    banner.set_revealed(True)
    banner.add_css_class("warning")
    return banner


def build_linuwu_sense_banner() -> Adw.Banner:
    """linuwu_sense module missing (warning, read-only). No button.

    Fan control requires linuwu_sense (community DKMS module) — the stock
    acer_wmi kernel module does not expose predator_sense/fan_speed.
    """
    banner = Adw.Banner.new(
        "Fan control unavailable: install the linuwu_sense kernel module."
    )
    banner.set_revealed(True)
    banner.add_css_class("warning")
    return banner


def show_ppd_explainer(parent_window) -> None:
    """Open the in-app 'About power-profiles-daemon' explainer dialog.

    Triggered from MainWindow's HeaderBar primary menu (Landmine #1 fallback).
    No external URL — embedded copy only.

    Body text VERBATIM from 03-UI-SPEC.md § Learn-more Dialog.
    """
    window = Adw.Window()
    window.set_title("About power-profiles-daemon")
    window.set_default_size(480, 360)
    window.set_modal(True)
    window.set_transient_for(parent_window)

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    toolbar.add_top_bar(header)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_hexpand(True)
    scrolled.set_vexpand(True)
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    body = Gtk.Label()
    body.set_wrap(True)
    body.set_xalign(0.0)
    body.set_margin_top(12)
    body.set_margin_bottom(12)
    body.set_margin_start(12)
    body.set_margin_end(12)
    body.set_text(
        "power-profiles-daemon (PPD) is a system service that manages "
        "performance profiles for laptops. AcerControl writes directly to "
        "/sys/firmware/acpi/platform_profile; PPD also writes to that file "
        "in response to its own logic, which can silently revert your "
        "selection.\n\n"
        "“Disable PPD” runs systemctl mask --now "
        "power-profiles-daemon.service, which is reversible. To restore "
        "PPD later: sudo systemctl unmask power-profiles-daemon.\n\n"
        "In AcerControl v1+, the boot service acer-performance.service "
        "will declare Conflicts=power-profiles-daemon.service so this "
        "becomes automatic."
    )
    scrolled.set_child(body)
    toolbar.set_content(scrolled)
    window.set_content(toolbar)

    # Escape closes — default Adwaita HeaderBar provides a close button.
    window.present()
