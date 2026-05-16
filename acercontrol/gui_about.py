# acercontrol/gui_about.py — Phase 3
"""About dialog with Diagnostics carve-out (GUI-08 exempt zone).

Adw.AboutDialog.set_debug_info(json_str) is the upstream-blessed slot
for raw kernel profile values to render. This module is the ONLY place
in the GUI where literals like "low-power" / "performance" may appear
in user-visible text (via probe() JSON serialization).

Landmine #7: dialog.present(parent_window) — NOT dialog.present().
Adw.Dialog requires a parent arg since libadwaita 1.5.
"""
from __future__ import annotations

import json

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from acercontrol import __version__
from acercontrol.features import probe, FeatureReport


def _report_to_dict(report: FeatureReport) -> dict:
    """Serialise FeatureReport to the same dict shape acercontrol.cli's
    cmd_status uses for --json output. Single source of truth.
    """
    return {
        "ok": report.ok,
        "checks": [
            {
                "name": c.name,
                "present": c.present,
                "detail": c.detail,
                "fix": c.fix,
                "severity": c.severity,
            }
            for c in report.checks
        ],
        "first_blocking_failure": (
            None if report.first_blocking_failure is None
            else {
                "name": report.first_blocking_failure.name,
                "fix": report.first_blocking_failure.fix,
            }
        ),
        "blacklist_entries": [
            {"file": p, "line": l} for p, l in report.blacklist_entries
        ],
    }


def build_about_dialog() -> Adw.AboutDialog:
    """Construct the About dialog. Diagnostics rendered via
    set_debug_info() — GUI-08 carve-out.
    """
    dialog = Adw.AboutDialog()
    dialog.set_application_name("AcerControl")
    dialog.set_version(__version__)
    dialog.set_developer_name("AcerControl contributors")
    dialog.set_copyright("© 2026 AcerControl contributors")
    dialog.set_license_type(Gtk.License.GPL_3_0)
    # GUI-08 carve-out: raw kernel values land here, only here.
    debug_json = json.dumps(_report_to_dict(probe()), indent=2)
    dialog.set_debug_info(debug_json)
    return dialog


def show_about(parent_window) -> None:
    """Triggered from HeaderBar primary menu → 'About AcerControl'.

    Landmine #7: present(parent) — never present().
    """
    build_about_dialog().present(parent_window)
