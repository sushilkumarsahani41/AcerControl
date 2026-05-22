# acercontrol/gui_sensors.py
"""Live sensor panel for CPU package, Acer temperatures, and fan RPMs."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from acercontrol.core import SensorReading


TEMP_WARM_C = 70
TEMP_HOT_C = 85
FAN_MAX_RPM = 8000

_SENSOR_CLASSES = ("sensor-ok", "sensor-warm", "sensor-hot")
_CSS_INSTALLED = False


def _ensure_sensor_css() -> None:
    global _CSS_INSTALLED
    if _CSS_INSTALLED:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(
        b"""
        progressbar.sensor-ok progress {
            background-color: #2ec27e;
        }
        progressbar.sensor-warm progress {
            background-color: #e5a50a;
        }
        progressbar.sensor-hot progress {
            background-color: #e01b24;
        }
        """
    )
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _CSS_INSTALLED = True


def _clamp_fraction(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, value / maximum))


class _SensorRow(Gtk.Box):
    def __init__(self, label: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_size_request(-1, 56)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self._label = Gtk.Label(label=label, xalign=0.0)
        self._label.set_hexpand(True)
        header.append(self._label)

        self._value_label = Gtk.Label(label="-", xalign=1.0)
        self._value_label.add_css_class("numeric")
        self._value_label.add_css_class("heading")
        header.append(self._value_label)

        self._bar = Gtk.ProgressBar()
        self._bar.set_hexpand(True)
        self._bar.set_show_text(False)
        self._bar.set_fraction(0.0)

        self.append(header)
        self.append(self._bar)

    def set_temperature(self, value_c: float | None) -> None:
        if value_c is None:
            self._value_label.set_text("-")
            self._bar.set_fraction(0.0)
            self._set_state_class(None)
            return

        self._value_label.set_text(f"{int(round(value_c))} C")
        self._bar.set_fraction(_clamp_fraction(float(value_c), 100.0))
        if value_c < TEMP_WARM_C:
            self._set_state_class("sensor-ok")
        elif value_c < TEMP_HOT_C:
            self._set_state_class("sensor-warm")
        else:
            self._set_state_class("sensor-hot")

    def set_fan(self, rpm: int | None) -> None:
        if rpm is None:
            self._value_label.set_text("-")
            self._bar.set_fraction(0.0)
            return

        self._value_label.set_text(f"{int(rpm)} RPM")
        self._bar.set_fraction(_clamp_fraction(float(rpm), FAN_MAX_RPM))

    def _set_state_class(self, css_class: str | None) -> None:
        for existing in _SENSOR_CLASSES:
            self._bar.remove_css_class(existing)
        if css_class is not None:
            self._bar.add_css_class(css_class)


class SensorPanel(Adw.PreferencesGroup):
    """Stable read-only sensor rows updated by MainWindow's refresh timer."""

    def __init__(self, _window=None) -> None:
        super().__init__()
        _ensure_sensor_css()

        self.set_title("Sensors")
        self.set_description("Live refresh: 2 s")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(16)
        content.set_margin_end(16)

        self._cpu_package = _SensorRow("CPU Package")
        self._acer_temp1 = _SensorRow("Acer Temp 1")
        self._acer_temp2 = _SensorRow("Acer Temp 2")
        self._acer_temp3 = _SensorRow("Acer Temp 3")
        self._fan1 = _SensorRow("Fan 1")
        self._fan2 = _SensorRow("Fan 2")

        for row in (
            self._cpu_package,
            self._acer_temp1,
            self._acer_temp2,
            self._acer_temp3,
            self._fan1,
            self._fan2,
        ):
            content.append(row)

        self.add(content)

    def update(self, reading: SensorReading) -> None:
        self._cpu_package.set_temperature(reading.cpu_package_c)
        self._acer_temp1.set_temperature(reading.acer_temp1_c)
        self._acer_temp2.set_temperature(reading.acer_temp2_c)
        self._acer_temp3.set_temperature(reading.acer_temp3_c)
        self._fan1.set_fan(reading.fan1_rpm)
        self._fan2.set_fan(reading.fan2_rpm)
