"""Fan control panel — AUTO / MAX / MANUAL %.

Mirrors the CLI `fan set` command. Writes through the acercontrol-setfan
privileged wrapper (pkexec/sudo). MANUAL mode exposes a 0-100 slider.

The current state is read from /sys/devices/platform/acer-wmi/predator_sense/
fan_speed (format: "cpu_pct,gpu_pct"; 0,0 = auto, 100,100 = max, N,N = manual).
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from acercontrol.privilege import run_privileged


FAN_SPEED_PATH = "/sys/devices/platform/acer-wmi/predator_sense/fan_speed"


def read_fan_speed() -> tuple[int, int] | None:
    """Parse the predator_sense fan_speed sysfs file. None if missing."""
    try:
        raw = open(FAN_SPEED_PATH).read().strip()
        parts = raw.split(",")
        return int(parts[0]), int(parts[1])
    except (OSError, ValueError, IndexError):
        return None


def classify_mode(cpu: int, gpu: int) -> str:
    if cpu == 0 and gpu == 0:
        return "auto"
    if cpu == 100 and gpu == 100:
        return "max"
    return "manual"


class FanControlPanel(Adw.PreferencesGroup):
    """Three-button mode picker + manual slider, written through the wrapper."""

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._pending = False
        self._buttons: dict[str, Gtk.Button] = {}
        self._suppress_slider_signal = False

        self.set_title("FAN CONTROL")
        self.set_description("Independent of the platform profile")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        # Mode buttons row
        self._mode_row = Gtk.FlowBox()
        self._mode_row.set_selection_mode(Gtk.SelectionMode.NONE)
        self._mode_row.set_column_spacing(8)
        self._mode_row.set_row_spacing(8)
        self._mode_row.set_min_children_per_line(1)
        self._mode_row.set_max_children_per_line(3)
        self._mode_row.set_homogeneous(True)
        content.append(self._mode_row)

        for mode in ("auto", "max", "manual"):
            button = Gtk.Button(label=mode.upper())
            button.add_css_class("pill")
            button.add_css_class(f"profile-{'turbo' if mode == 'max' else 'eco' if mode == 'auto' else 'balanced'}")
            button.set_size_request(132, 60)
            button.set_tooltip_text(f"Fan mode: {mode}")
            button.connect("clicked", self._on_mode_clicked, mode)
            self._buttons[mode] = button
            self._mode_row.append(button)

        # Manual slider row (hidden until manual mode is active or being set)
        self._slider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        slider_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        slider_label = Gtk.Label(label="Manual speed", xalign=0.0)
        slider_label.set_hexpand(True)
        slider_label.add_css_class("dim-label")
        slider_header.append(slider_label)

        self._slider_value_label = Gtk.Label(label="50%", xalign=1.0)
        self._slider_value_label.add_css_class("numeric")
        self._slider_value_label.add_css_class("heading")
        slider_header.append(self._slider_value_label)
        self._slider_box.append(slider_header)

        adjustment = Gtk.Adjustment(value=50, lower=0, upper=100, step_increment=5, page_increment=10)
        self._slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
        self._slider.set_draw_value(False)
        self._slider.set_hexpand(True)
        self._slider.add_mark(0, Gtk.PositionType.BOTTOM, None)
        self._slider.add_mark(50, Gtk.PositionType.BOTTOM, None)
        self._slider.add_mark(100, Gtk.PositionType.BOTTOM, None)
        self._slider.connect("value-changed", self._on_slider_value_changed)

        # commit-on-release (not on every drag tick) keeps polkit prompts sane
        gesture = Gtk.GestureClick()
        gesture.set_button(1)
        gesture.connect("released", self._on_slider_released)
        self._slider.add_controller(gesture)
        self._slider_box.append(self._slider)

        content.append(self._slider_box)

        # Status / pending row
        self._status_label = Gtk.Label(xalign=0.0)
        self._status_label.add_css_class("dim-label")
        content.append(self._status_label)

        self.add(content)
        self.refresh()

    def refresh(self) -> None:
        speeds = read_fan_speed()
        if speeds is None:
            self._status_label.set_text("Fan control unavailable (predator_sense missing)")
            for b in self._buttons.values():
                b.set_sensitive(False)
            self._slider_box.set_visible(False)
            return

        for b in self._buttons.values():
            b.set_sensitive(not self._pending)

        cpu, gpu = speeds
        mode = classify_mode(cpu, gpu)
        for name, button in self._buttons.items():
            if name == mode:
                button.add_css_class("suggested-action")
            else:
                button.remove_css_class("suggested-action")

        self._slider_box.set_visible(mode == "manual")
        if mode == "manual":
            self._suppress_slider_signal = True
            self._slider.set_value(cpu)
            self._slider_value_label.set_text(f"{cpu}%")
            self._suppress_slider_signal = False

        if cpu != gpu:
            self._status_label.set_text(f"CPU {cpu}%   GPU {gpu}%")
        else:
            self._status_label.set_text("")

    def _on_mode_clicked(self, _button: Gtk.Button, mode: str) -> None:
        if self._pending:
            return
        if mode == "manual":
            speed = int(self._slider.get_value())
            self._invoke_set(["acercontrol-setfan", "manual", str(speed)], mode)
        else:
            self._invoke_set(["acercontrol-setfan", mode], mode)

    def _on_slider_value_changed(self, scale: Gtk.Scale) -> None:
        if self._suppress_slider_signal:
            return
        value = int(scale.get_value())
        self._slider_value_label.set_text(f"{value}%")

    def _on_slider_released(self, _gesture, _n_press, _x, _y) -> None:
        if self._pending:
            return
        speeds = read_fan_speed()
        if speeds is None:
            return
        current_mode = classify_mode(*speeds)
        if current_mode != "manual":
            # Slider committed but we're not in manual mode yet — ignore.
            return
        speed = int(self._slider.get_value())
        if speed == speeds[0]:
            return
        self._invoke_set(["acercontrol-setfan", "manual", str(speed)], "manual")

    def _invoke_set(self, wrapper_argv: list[str], mode: str) -> None:
        self._pending = True
        for b in self._buttons.values():
            b.set_sensitive(False)
        self._status_label.set_text("Awaiting authorisation...")

        result = run_privileged(wrapper_argv)

        self._pending = False
        if result.cancelled:
            self._status_label.set_text("")
            self._toast("Authorisation cancelled")
            self.refresh()
            return
        if result.returncode != 0:
            self._status_label.set_text("")
            self._toast("Fan change failed. See terminal for details.")
            self.refresh()
            return

        # Brief delay so the kernel updates the sysfs read-back
        GLib.timeout_add(150, self._verify_after_set, mode)

    def _verify_after_set(self, mode: str):
        self.refresh()
        speeds = read_fan_speed()
        if speeds is not None:
            label = classify_mode(*speeds)
            if label == "manual":
                self._toast(f"Fan set to manual {speeds[0]}%")
            else:
                self._toast(f"Fan set to {label}")
        return GLib.SOURCE_REMOVE

    def _toast(self, message: str) -> None:
        if hasattr(self._window, "show_toast"):
            self._window.show_toast(message)
