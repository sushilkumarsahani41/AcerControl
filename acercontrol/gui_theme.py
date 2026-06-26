"""Predator gaming theme — forces dark mode + custom CSS overlay.

Loaded once by gui.py on application startup. Uses GTK4 CSS with @define-color
and the alpha() function (Adwaita 1.5+ on Ubuntu 24.04).

Color palette mirrors the Predator hardware brand:
  - Deep black backgrounds with subtle teal radial glow
  - Predator cyan (#00d4ff) as the primary accent
  - Turbo orange (#ff6b1f) for the turbo profile / hot states
  - Neon green/yellow/red for sensor traffic-light states
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402


_APPLIED = False


PREDATOR_CSS = b"""
/* === Predator palette =================================================== */
@define-color predator_black #07090c;
@define-color predator_dark #0d1117;
@define-color predator_card #141a23;
@define-color predator_card_hover #1c2430;
@define-color predator_border #1f2937;
@define-color predator_border_bright #2a3848;

@define-color predator_teal #00d4ff;
@define-color predator_teal_dim #0099b8;

@define-color predator_orange #ff6b1f;
@define-color predator_red #ff003c;
@define-color predator_green #00ff88;
@define-color predator_yellow #ffcc00;

@define-color predator_text #e6edf3;
@define-color predator_text_dim #8b949e;
@define-color predator_text_faint #4d5666;

/* === Window background ================================================== */
window,
window.background,
.background {
    background-color: @predator_black;
    background-image:
        radial-gradient(circle at 15% -10%, alpha(@predator_teal, 0.10) 0%, transparent 45%),
        radial-gradient(circle at 85% 110%, alpha(@predator_orange, 0.05) 0%, transparent 50%);
    color: @predator_text;
}

/* === Header bar ========================================================= */
headerbar {
    background-color: alpha(@predator_dark, 0.92);
    border-bottom: 1px solid alpha(@predator_teal, 0.35);
    box-shadow: 0 1px 12px alpha(@predator_teal, 0.18);
    color: @predator_text;
    min-height: 46px;
    padding: 0 12px;
}

headerbar windowtitle,
headerbar > windowhandle > box > box.start > label,
headerbar > windowhandle > box > box.end > label,
headerbar label.title {
    color: @predator_text;
    font-weight: bold;
    font-size: 13px;
}

headerbar button {
    background: transparent;
    color: @predator_text_dim;
    border: 1px solid transparent;
    border-radius: 3px;
}

headerbar button:hover {
    background-color: alpha(@predator_teal, 0.12);
    border-color: alpha(@predator_teal, 0.4);
    color: @predator_teal;
}

/* === Generic labels ===================================================== */
label.dim-label,
.dim-label {
    color: @predator_text_dim;
}

label.heading {
    color: @predator_teal;
    font-weight: 800;
    letter-spacing: 1px;
}

label.numeric,
.numeric {
    font-family: "JetBrains Mono", "Fira Mono", "Cascadia Mono", monospace;
    color: @predator_teal;
    font-weight: bold;
    font-size: 15px;
}

/* === PreferencesGroup card surface ====================================== */
preferencesgroup > box > label.heading {
    color: @predator_teal;
    font-weight: 900;
    font-size: 12px;
    letter-spacing: 2px;
}

list.boxed-list,
preferencesgroup list {
    background-color: alpha(@predator_card, 0.85);
    border: 1px solid @predator_border;
    border-radius: 6px;
    color: @predator_text;
}

row,
row.activatable,
list.boxed-list > row {
    background-color: transparent;
    color: @predator_text;
    border-bottom: 1px solid @predator_border;
}

row:hover,
row.activatable:hover {
    background-color: alpha(@predator_teal, 0.06);
}

/* === Profile pill buttons =============================================== */
button.pill {
    background-image: linear-gradient(180deg, @predator_card_hover 0%, @predator_card 100%);
    border: 1px solid @predator_border_bright;
    border-radius: 4px;
    color: @predator_text_dim;
    font-weight: 800;
    padding: 14px 20px;
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.6);
    transition: all 140ms cubic-bezier(0.4, 0, 0.2, 1);
}

button.pill:hover {
    background-image: linear-gradient(180deg, @predator_border_bright 0%, @predator_card_hover 100%);
    border-color: alpha(@predator_teal, 0.6);
    color: @predator_teal;
    box-shadow: 0 0 14px alpha(@predator_teal, 0.30);
}

button.pill:disabled {
    background-image: none;
    background-color: @predator_card;
    color: @predator_text_faint;
    border-color: @predator_border;
    box-shadow: none;
}

/* Active profile - solid Predator teal glow */
button.pill.suggested-action,
button.pill.suggested-action:hover {
    background-image: linear-gradient(180deg, @predator_teal 0%, @predator_teal_dim 100%);
    border: 1px solid @predator_teal;
    color: @predator_black;
    text-shadow: none;
    box-shadow:
        0 0 0 1px alpha(@predator_teal, 0.5),
        0 0 18px alpha(@predator_teal, 0.55),
        inset 0 1px 0 alpha(white, 0.25);
}

/* Turbo profile - orange/red neon when active */
button.pill.profile-turbo.suggested-action,
button.pill.profile-turbo.suggested-action:hover {
    background-image: linear-gradient(180deg, @predator_orange 0%, #c43800 100%);
    border-color: @predator_orange;
    color: white;
    text-shadow: 0 0 8px alpha(@predator_red, 0.6);
    box-shadow:
        0 0 0 1px alpha(@predator_orange, 0.5),
        0 0 22px alpha(@predator_orange, 0.65),
        inset 0 1px 0 alpha(white, 0.2);
}

/* Eco profile - green when active */
button.pill.profile-eco.suggested-action,
button.pill.profile-eco.suggested-action:hover {
    background-image: linear-gradient(180deg, @predator_green 0%, #00a85a 100%);
    border-color: @predator_green;
    color: @predator_black;
    box-shadow:
        0 0 0 1px alpha(@predator_green, 0.5),
        0 0 18px alpha(@predator_green, 0.55),
        inset 0 1px 0 alpha(white, 0.25);
}

/* === Generic buttons ==================================================== */
button {
    background-image: linear-gradient(180deg, @predator_card_hover 0%, @predator_card 100%);
    border: 1px solid @predator_border_bright;
    border-radius: 4px;
    color: @predator_text;
    font-weight: 600;
    padding: 8px 16px;
}

button:hover {
    border-color: alpha(@predator_teal, 0.6);
    color: @predator_teal;
    box-shadow: 0 0 10px alpha(@predator_teal, 0.25);
}

button.suggested-action {
    background-image: linear-gradient(180deg, @predator_teal 0%, @predator_teal_dim 100%);
    border-color: @predator_teal;
    color: @predator_black;
    font-weight: 800;
}

button.destructive-action {
    background-image: linear-gradient(180deg, @predator_red 0%, #b30029 100%);
    border-color: @predator_red;
    color: white;
}

button.flat {
    background-image: none;
    background-color: transparent;
    border-color: transparent;
}

button.flat:hover {
    background-color: alpha(@predator_teal, 0.12);
    border-color: alpha(@predator_teal, 0.3);
}

/* === Progress bars (sensor + fan) ======================================= */
progressbar {
    min-height: 10px;
}

progressbar > trough {
    background-color: @predator_card;
    border: 1px solid @predator_border;
    border-radius: 2px;
    min-height: 8px;
    min-width: 60px;
}

progressbar > trough > progress {
    background-image: linear-gradient(90deg, @predator_teal_dim 0%, @predator_teal 100%);
    border-radius: 2px;
    min-height: 8px;
    box-shadow: 0 0 6px alpha(@predator_teal, 0.45);
}

progressbar.sensor-ok > trough > progress {
    background-image: linear-gradient(90deg, #00a85a 0%, @predator_green 100%);
    box-shadow: 0 0 6px alpha(@predator_green, 0.5);
}

progressbar.sensor-warm > trough > progress {
    background-image: linear-gradient(90deg, #c89a00 0%, @predator_yellow 100%);
    box-shadow: 0 0 6px alpha(@predator_yellow, 0.5);
}

progressbar.sensor-hot > trough > progress {
    background-image: linear-gradient(90deg, @predator_red 0%, #ff5566 100%);
    box-shadow: 0 0 10px alpha(@predator_red, 0.7);
}

/* === Sliders (fan manual mode) ========================================== */
scale > trough {
    background-color: @predator_card;
    border: 1px solid @predator_border;
    border-radius: 2px;
    min-height: 6px;
}

scale > trough > highlight {
    background-image: linear-gradient(90deg, @predator_teal_dim 0%, @predator_teal 100%);
    border-radius: 2px;
    box-shadow: 0 0 6px alpha(@predator_teal, 0.45);
}

scale > trough > slider {
    background-color: @predator_teal;
    border: 2px solid @predator_dark;
    border-radius: 50%;
    min-height: 16px;
    min-width: 16px;
    box-shadow: 0 0 8px alpha(@predator_teal, 0.7);
}

/* === Switches =========================================================== */
switch {
    background-color: @predator_card;
    border: 1px solid @predator_border_bright;
    border-radius: 12px;
}

switch:checked {
    background-color: @predator_teal_dim;
    border-color: @predator_teal;
    box-shadow: 0 0 8px alpha(@predator_teal, 0.4);
}

switch slider {
    background-color: @predator_text;
    border-radius: 50%;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
}

/* === Toast ============================================================== */
toast {
    background-color: @predator_dark;
    border: 1px solid alpha(@predator_teal, 0.4);
    border-radius: 4px;
    color: @predator_text;
    box-shadow: 0 4px 18px alpha(@predator_teal, 0.25);
}

/* === Banner ============================================================= */
banner > revealer > widget {
    background-image: linear-gradient(180deg, alpha(@predator_orange, 0.18) 0%, alpha(@predator_orange, 0.06) 100%);
    border-bottom: 1px solid alpha(@predator_orange, 0.7);
    color: @predator_text;
}

banner > revealer > widget button {
    background-image: none;
    background-color: alpha(@predator_orange, 0.25);
    border-color: @predator_orange;
    color: white;
}

/* === StatusPage (blocker screens) ======================================= */
statuspage {
    background-color: transparent;
}

statuspage > scrolledwindow > viewport > box > clamp > box > box > label.title {
    color: @predator_teal;
}

/* === ScrolledWindow scrollbar =========================================== */
scrollbar slider {
    background-color: @predator_border_bright;
    border-radius: 4px;
    min-width: 6px;
    min-height: 6px;
}

scrollbar slider:hover {
    background-color: @predator_teal_dim;
}
"""


def apply_predator_theme(app: "Adw.Application | None" = None) -> None:
    """Force dark color scheme and inject the Predator CSS overlay.

    Idempotent — safe to call multiple times. The CSS provider is registered
    once per Gdk.Display at USER priority so it overrides Adwaita's defaults
    without forking the Adwaita stylesheet.
    """
    global _APPLIED
    if _APPLIED:
        return

    style_manager = Adw.StyleManager.get_default()
    style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    display = Gdk.Display.get_default()
    if display is None:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(PREDATOR_CSS)
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER,
    )

    _APPLIED = True
