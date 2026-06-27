"""Keyboard RGB control panel — four_zoned_kb mode + per-zone colors.

Writes through the acercontrol-setkbd privileged wrapper (pkexec/sudo).
Reads state from /sys/devices/platform/acer-wmi/four_zoned_kb/four_zone_mode.

Layout:
  - Mode pill buttons (static, breathing, neon, wave, shifting, zoom,
    meteor, twinkling) — active mode glows Predator cyan
  - Color picker + brightness/speed sliders + direction radio
  - APPLY / OFF buttons
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from acercontrol.privilege import run_privileged


FOUR_ZONE_PATH = "/sys/devices/platform/acer-wmi/four_zoned_kb/four_zone_mode"

KBD_MODES = (
    ("static",    0),
    ("breathing", 1),
    ("neon",      2),
    ("wave",      3),
    ("shifting",  4),
    ("zoom",      5),
    ("meteor",    6),
    ("twinkling", 7),
)
KBD_MODE_NAMES = {v: k for k, v in KBD_MODES}


def read_four_zone() -> tuple[int, int, int, int, int, int, int] | None:
    try:
        raw = open(FOUR_ZONE_PATH).read().strip()
        parts = [int(x) for x in raw.split(",")]
        if len(parts) != 7:
            return None
        return tuple(parts)  # type: ignore[return-value]
    except (OSError, ValueError):
        return None


def rgba_to_hex(rgba: Gdk.RGBA) -> tuple[int, int, int]:
    return (
        int(round(rgba.red * 255)),
        int(round(rgba.green * 255)),
        int(round(rgba.blue * 255)),
    )


class KeyboardPanel(Adw.PreferencesGroup):
    """Pill-button mode picker + color/brightness/speed sliders."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._pending = False
        self._mode_buttons: dict[str, Gtk.Button] = {}
        self._selected_mode = "static"

        self.set_title("KEYBOARD LIGHTING")
        self.set_description("Four-zone RGB via linuwu_sense")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        # Mode row
        self._mode_row = Gtk.FlowBox()
        self._mode_row.set_selection_mode(Gtk.SelectionMode.NONE)
        self._mode_row.set_column_spacing(8)
        self._mode_row.set_row_spacing(8)
        self._mode_row.set_min_children_per_line(2)
        self._mode_row.set_max_children_per_line(4)
        self._mode_row.set_homogeneous(True)
        content.append(self._mode_row)

        for name, _ in KBD_MODES:
            button = Gtk.Button(label=name.upper())
            button.add_css_class("pill")
            button.set_size_request(120, 48)
            button.connect("clicked", self._on_mode_clicked, name)
            self._mode_buttons[name] = button
            self._mode_row.append(button)

        # Color picker
        color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        color_label = Gtk.Label(label="Color", xalign=0.0)
        color_label.add_css_class("dim-label")
        color_label.set_hexpand(False)
        color_box.append(color_label)

        self._color_button = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.parse("#00d4ff")  # Predator cyan default
        self._color_button.set_rgba(rgba)
        self._color_button.set_use_alpha(False)
        color_box.append(self._color_button)

        self._color_hex_label = Gtk.Label(label="#00d4ff", xalign=0.0)
        self._color_hex_label.add_css_class("numeric")
        self._color_hex_label.set_hexpand(True)
        color_box.append(self._color_hex_label)
        self._color_button.connect("color-set", self._on_color_changed)

        content.append(color_box)

        # Brightness slider
        content.append(self._make_slider_row(
            "Brightness", 0, 100, 100, "_brightness_scale", "_brightness_value",
        ))

        # Speed slider
        content.append(self._make_slider_row(
            "Speed", 0, 9, 5, "_speed_scale", "_speed_value",
        ))

        # Direction row
        dir_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        dir_label = Gtk.Label(label="Direction", xalign=0.0)
        dir_label.add_css_class("dim-label")
        dir_label.set_hexpand(True)
        dir_box.append(dir_label)

        self._dir_buttons: dict[int, Gtk.ToggleButton] = {}
        for value, text in ((0, "AUTO"), (1, "LEFT"), (2, "RIGHT")):
            tb = Gtk.ToggleButton(label=text)
            tb.add_css_class("pill")
            tb.set_size_request(80, 36)
            tb.connect("toggled", self._on_direction_toggled, value)
            self._dir_buttons[value] = tb
            dir_box.append(tb)
        self._dir_buttons[1].set_active(True)
        self._selected_direction = 1
        content.append(dir_box)

        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_box.set_halign(Gtk.Align.END)

        self._apply_button = Gtk.Button(label="APPLY")
        self._apply_button.add_css_class("suggested-action")
        self._apply_button.add_css_class("pill")
        self._apply_button.set_size_request(120, 44)
        self._apply_button.connect("clicked", self._on_apply_clicked)
        action_box.append(self._apply_button)

        self._off_button = Gtk.Button(label="OFF")
        self._off_button.add_css_class("pill")
        self._off_button.set_size_request(120, 44)
        self._off_button.connect("clicked", self._on_off_clicked)
        action_box.append(self._off_button)

        content.append(action_box)

        # Status
        self._status_label = Gtk.Label(xalign=0.0)
        self._status_label.add_css_class("dim-label")
        content.append(self._status_label)

        self.add(content)
        self.refresh()

    def _make_slider_row(self, title: str, lo: int, hi: int, default: int,
                         scale_attr: str, value_attr: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label=title, xalign=0.0)
        label.add_css_class("dim-label")
        label.set_hexpand(True)
        header.append(label)

        value_label = Gtk.Label(label=str(default), xalign=1.0)
        value_label.add_css_class("numeric")
        value_label.add_css_class("heading")
        header.append(value_label)
        row.append(header)

        adj = Gtk.Adjustment(value=default, lower=lo, upper=hi,
                             step_increment=1, page_increment=5)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.connect("value-changed",
                      lambda s: value_label.set_text(str(int(s.get_value()))))
        row.append(scale)

        setattr(self, scale_attr, scale)
        setattr(self, value_attr, value_label)
        return row

    def refresh(self) -> None:
        state = read_four_zone()
        if state is None:
            self._status_label.set_text(
                "Keyboard RGB unavailable (linuwu_sense not loaded)"
            )
            for b in self._mode_buttons.values():
                b.set_sensitive(False)
            self._apply_button.set_sensitive(False)
            self._off_button.set_sensitive(False)
            return

        mode_id, speed, brightness, direction, r, g, b = state
        active_name = KBD_MODE_NAMES.get(mode_id, "static")
        self._select_mode(active_name)

        # Sync the controls to live state
        if 0 <= speed <= 9:
            self._speed_scale.set_value(speed)
        if 0 <= brightness <= 100:
            self._brightness_scale.set_value(brightness)
        if direction in self._dir_buttons:
            self._set_direction(direction)

        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue, rgba.alpha = r / 255, g / 255, b / 255, 1.0
        self._color_button.set_rgba(rgba)
        self._color_hex_label.set_text(f"#{r:02x}{g:02x}{b:02x}")

    def _select_mode(self, name: str) -> None:
        self._selected_mode = name
        for n, button in self._mode_buttons.items():
            if n == name:
                button.add_css_class("suggested-action")
            else:
                button.remove_css_class("suggested-action")

    def _set_direction(self, value: int) -> None:
        self._selected_direction = value
        for v, btn in self._dir_buttons.items():
            # Avoid notify-on-toggle recursion by checking first
            if btn.get_active() != (v == value):
                btn.set_active(v == value)

    def _on_mode_clicked(self, _button, name: str) -> None:
        self._select_mode(name)

    def _on_direction_toggled(self, button: Gtk.ToggleButton, value: int) -> None:
        if button.get_active():
            self._set_direction(value)

    def _on_color_changed(self, _button) -> None:
        r, g, b = rgba_to_hex(self._color_button.get_rgba())
        self._color_hex_label.set_text(f"#{r:02x}{g:02x}{b:02x}")

    def _on_apply_clicked(self, _button) -> None:
        if self._pending:
            return
        r, g, b = rgba_to_hex(self._color_button.get_rgba())
        mode_id = dict(KBD_MODES)[self._selected_mode]
        wrapper_argv = [
            "acercontrol-setkbd", "mode",
            str(mode_id),
            str(int(self._speed_scale.get_value())),
            str(int(self._brightness_scale.get_value())),
            str(self._selected_direction),
            str(r), str(g), str(b),
        ]
        # Cross-field rule
        if self._selected_mode in ("wave", "shifting") and self._selected_direction == 0:
            self._toast("Wave/shifting modes need direction LEFT or RIGHT")
            return
        self._invoke(wrapper_argv, label=f"{self._selected_mode} applied")

    def _on_off_clicked(self, _button) -> None:
        if self._pending:
            return
        state = read_four_zone()
        if state is not None:
            mode_id, speed, _, direction, r, g, b = state
        else:
            mode_id, speed, direction, r, g, b = 0, 0, 0, 0, 0, 0
        wrapper_argv = [
            "acercontrol-setkbd", "mode",
            str(mode_id), str(speed), "0", str(direction),
            str(r), str(g), str(b),
        ]
        self._invoke(wrapper_argv, label="Keyboard off")

    def _invoke(self, wrapper_argv: list[str], *, label: str) -> None:
        self._pending = True
        self._apply_button.set_sensitive(False)
        self._off_button.set_sensitive(False)
        self._status_label.set_text("Awaiting authorisation...")

        result = run_privileged(wrapper_argv)

        self._pending = False
        self._apply_button.set_sensitive(True)
        self._off_button.set_sensitive(True)

        if result.cancelled:
            self._status_label.set_text("")
            self._toast("Authorisation cancelled")
            return
        if result.returncode != 0:
            self._status_label.set_text("")
            self._toast("Keyboard change failed. See terminal.")
            return

        # Brief delay to let the kernel sysfs settle
        GLib.timeout_add(150, self._after_apply, label)

    def _after_apply(self, label: str):
        self.refresh()
        self._status_label.set_text("")
        self._toast(label)
        return GLib.SOURCE_REMOVE

    def _toast(self, message: str) -> None:
        if hasattr(self._window, "show_toast"):
            self._window.show_toast(message)
