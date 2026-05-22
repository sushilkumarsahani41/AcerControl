# acercontrol/gui_window.py — Phase 3
"""MainWindow — Adw.ApplicationWindow with probe-first routing (GUI-01, GUI-03, GUI-04).

Lifecycle:
  1. __init__ constructs ToolbarView(HeaderBar + ToastOverlay(Stack)).
  2. _route(probe()) runs FIRST and chooses blocker StatusPage vs main view.
  3. Signal handlers (_on_disable_ppd_clicked, _on_reload_acer_wmi_clicked)
     invoke privilege.run_privileged() synchronously and surface results
     via Adw.Toast.

Landmine #1 fallback: HeaderBar primary menu has 'About power-profiles-daemon'
entry that opens gui_banner.show_ppd_explainer() — replaces the unsupported
Pango link in the banner title.

show_ppd_banner(force=False) is the Phase 4 contract — Phase 4's mismatch
handler will call this with force=True on PPD-revert detection.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from acercontrol.core import read_profile, read_sensors
from acercontrol.features import probe, FeatureReport
from acercontrol.profiles import PROFILES, Profile
from acercontrol.privilege import run_privileged
from acercontrol.systemd import wait_for_boot_service

from acercontrol.gui_status_pages import (
    BLOCKER_FACTORIES,
)
from acercontrol.gui_boot import BootServicePanel
from acercontrol.gui_notifications import CriticalTempNotifier, ProfileChangeNotifier
from acercontrol.gui_profiles import ProfileControlPanel
from acercontrol.gui_resume import ResumeReapplyController
from acercontrol.gui_sensors import SensorPanel
from acercontrol.gui_banner import (
    build_ppd_banner,
    build_blacklist_banner,
    build_coretemp_banner,
    show_ppd_explainer,
)
from acercontrol.gui_about import show_about


class MainWindow(Adw.ApplicationWindow):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("AcerControl")
        self.set_default_size(800, 600)

        # In-memory PPD-banner-dismissed flag (CONTEXT D-04). No config file.
        self._ppd_banner_dismissed = False
        self._ppd_banner: Adw.Banner | None = None
        self._profile_notifier = ProfileChangeNotifier(self)
        self._critical_notifier = CriticalTempNotifier(self)
        self._sensor_source_id: int | None = None
        self._last_seen_profile_name: str | None = None
        initial_profile = read_profile()
        self._last_selected_profile_name = None
        if initial_profile is not Profile.CUSTOM:
            self._last_selected_profile_name = initial_profile.display
        self._boot_service_waited = False
        self._boot_service_ready = False
        self._resume_controller = ResumeReapplyController(self)

        # 3-region layout: HeaderBar + ToastOverlay(Stack)
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            primary=True,
        )
        menu_button.set_menu_model(self._build_primary_menu())
        header.pack_end(menu_button)
        toolbar.add_top_bar(header)

        self._toast_overlay = Adw.ToastOverlay()
        self._content_swapper = Gtk.Stack()
        self._toast_overlay.set_child(self._content_swapper)
        toolbar.set_content(self._toast_overlay)

        self.set_content(toolbar)

        # Pre-create the main profile control page and warning banner column.
        # Blocker pages are constructed lazily on demand inside _route.
        self._main_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_banners = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_column.append(self._main_banners)

        self._main_scroll = Gtk.ScrolledWindow()
        self._main_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._main_scroll.set_vexpand(True)

        self._main_page = Adw.PreferencesPage()
        self._main_page.set_margin_top(24)
        self._main_page.set_margin_bottom(24)
        self._main_page.set_margin_start(24)
        self._main_page.set_margin_end(24)

        self._profile_panel = ProfileControlPanel(self)
        self._sensor_panel = SensorPanel(self)
        self._boot_panel = BootServicePanel(self)
        self._main_page.add(self._profile_panel)
        self._main_page.add(self._sensor_panel)
        self._main_page.add(self._boot_panel)
        self._main_scroll.set_child(self._main_page)
        self._main_column.append(self._main_scroll)
        self._content_swapper.add_named(self._main_column, "main")
        self.connect("close-request", self._on_close_request)

        # GUI-03: probe FIRST, then route.
        self._route(probe())
        self._resume_controller.start()

    # ── Primary menu (Landmine #1 fallback + D-04 dismissibility) ────

    def _build_primary_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("About power-profiles-daemon", "win.about-ppd")
        menu.append("About AcerControl", "win.about")

        # D-04 — Option A: HeaderBar primary menu dismiss entry. Use
        # `Gio.MenuItem` (not menu.append) so we can set the
        # `hidden-when="action-disabled"` attribute — the entry then
        # disappears entirely when the GAction is disabled rather than
        # rendering grayed-out. The action's enabled-state is the
        # single visibility predicate; it is flipped from three sites:
        #   (1) here at creation: disabled (no banner exists yet)
        #   (2) `_rebuild_warning_banners` — enabled iff a PPD banner
        #       was appended to `_main_banners` in this pass
        #   (3) `_on_banner_revealed_change` — disabled when the user
        #       hides the banner (covers any future programmatic
        #       set_revealed(False) call too)
        # `show_ppd_banner(force=True)` flows through `_rebuild_warning_banners`
        # so the re-enable path is automatic.
        hide_item = Gio.MenuItem.new(
            "Hide PPD warning this session", "win.hide-ppd-banner"
        )
        hide_item.set_attribute_value(
            "hidden-when", GLib.Variant.new_string("action-disabled")
        )
        menu.append_item(hide_item)

        about_ppd = Gio.SimpleAction.new("about-ppd", None)
        about_ppd.connect("activate", lambda *_: show_ppd_explainer(self))
        self.add_action(about_ppd)

        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", lambda *_: show_about(self))
        self.add_action(about)

        # D-04 dismiss action — initially disabled (Site #1). Enabled by
        # `_rebuild_warning_banners` (Site #2); disabled by
        # `_on_banner_revealed_change` (Site #3). Handler explicitly sets
        # BOTH `set_revealed(False)` AND `_ppd_banner_dismissed = True`
        # per checker blocker (redundant with the notify handler but
        # explicit; both are idempotent).
        hide_action = Gio.SimpleAction.new("hide-ppd-banner", None)
        hide_action.set_enabled(False)
        hide_action.connect("activate", self._on_hide_ppd_banner_clicked)
        self.add_action(hide_action)

        return menu

    def _on_hide_ppd_banner_clicked(self, _action, _param) -> None:
        """Menu entry handler — hide the PPD banner this session."""
        if self._ppd_banner is not None:
            self._ppd_banner.set_revealed(False)
        self._ppd_banner_dismissed = True

    # ── Routing (CONTEXT D-03 severity-ordered hybrid) ────────────────

    def _route(self, report: FeatureReport) -> None:
        """Partition checks by severity. First blocker → full StatusPage;
        all-clear → main view with warning banners stacked on top.

        PPD check name VARIES (Phase 1 VERIFICATION lines 154-157): dispatch
        by severity + present, not by check name string match.
        """
        # Blocker — FeatureReport.ok is False
        if not report.ok:
            self._stop_sensor_refresh()
            blocker = report.first_blocking_failure
            assert blocker is not None  # ok=False implies at least one
            factory = BLOCKER_FACTORIES.get(blocker.name)
            if factory is None:
                # Unknown blocker name — fall back to placeholder with a toast
                self._content_swapper.set_visible_child_name("main")
                self._toast(f"Unhandled blocker: {blocker.name}")
                return
            page = factory(self)
            # Replace any previous blocker page in the stack
            child = self._content_swapper.get_child_by_name("blocker")
            if child is not None:
                self._content_swapper.remove(child)
            self._content_swapper.add_named(page, "blocker")
            self._content_swapper.set_visible_child_name("blocker")
            return

        # All blockers pass — render main view with stacked warning banners
        self._content_swapper.set_visible_child_name("main")
        self._rebuild_warning_banners(report)
        self.ensure_boot_service_ready()
        self._ensure_sensor_refresh()

    def _rebuild_warning_banners(self, report: FeatureReport) -> None:
        # Clear existing banners
        child = self._main_banners.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._main_banners.remove(child)
            child = nxt
        self._ppd_banner = None
        ppd_banner_added = False  # tracks whether the visibility predicate flips True

        # Walk checks; collect warning surfaces by (severity == "warning" and not present)
        for c in report.checks:
            if c.severity != "warning" or c.present:
                continue
            # Dispatch by name; PPD name varies between "power-profiles-daemon inactive"
            # (systemctl reachable) and "power-profiles-daemon state" (systemctl missing,
            # but that one is severity=info — won't reach here).
            if c.name.startswith("power-profiles-daemon"):
                if self._ppd_banner_dismissed:
                    continue
                banner = build_ppd_banner(self)
                self._ppd_banner = banner
                # Wire close-button → in-session dismissal
                banner.connect("notify::revealed", self._on_banner_revealed_change)
                self._main_banners.append(banner)
                ppd_banner_added = True
            elif c.name == "acer_wmi not blacklisted":
                self._main_banners.append(build_blacklist_banner())
            elif c.name == "coretemp hwmon":
                self._main_banners.append(build_coretemp_banner())

        # D-04 Site #2 — flip the dismiss GAction enabled-state in lockstep with
        # banner reveal-state. Enabled iff a PPD banner is currently shown AND
        # the user has not already dismissed this session.
        hide_action = self.lookup_action("hide-ppd-banner")
        if hide_action is not None:
            hide_action.set_enabled(ppd_banner_added)

    def _on_banner_revealed_change(self, banner: Adw.Banner, _pspec) -> None:
        if banner is self._ppd_banner and not banner.get_revealed():
            self._ppd_banner_dismissed = True
            # D-04 Site #3 — keep menu visibility predicate in sync.
            hide_action = self.lookup_action("hide-ppd-banner")
            if hide_action is not None:
                hide_action.set_enabled(False)

    def show_ppd_banner(self, force: bool = False) -> None:
        """Phase 4 contract: revert-on-mismatch handler calls this with
        force=True to override the in-session dismissed flag."""
        if force:
            self._ppd_banner_dismissed = False
        # Trigger a re-probe + re-render
        self._route(probe())
        if force and self._ppd_banner is not None:
            self._ppd_banner.set_revealed(True)

    # ── Signal handlers (mirror cli.py:233-256 shape; toast instead of print) ─

    def show_toast(self, message: str, *, timeout=None) -> None:
        toast = Adw.Toast.new(message)
        if timeout is not None:
            toast.set_timeout(timeout)
        self._toast_overlay.add_toast(toast)

    def _toast(self, message: str, *, timeout=None) -> None:
        self.show_toast(message, timeout=timeout)

    def is_focused(self) -> bool:
        return bool(self.is_active())

    def notify_profile_change(self, profile_name: str) -> None:
        self._last_seen_profile_name = profile_name
        if profile_name in PROFILES:
            self._last_selected_profile_name = profile_name
        self._profile_notifier.notify(profile_name)

    def ensure_boot_service_ready(self) -> bool:
        if self._boot_service_waited:
            return self._boot_service_ready
        self._boot_service_waited = True
        self._boot_service_ready = wait_for_boot_service()
        return self._boot_service_ready

    def reapply_last_profile_after_resume(self) -> None:
        last_selected = self._last_selected_profile_name
        if last_selected not in PROFILES:
            return

        actual = read_profile()
        if actual is not Profile.CUSTOM and actual.display == last_selected:
            self._last_seen_profile_name = last_selected
            return

        result = run_privileged(["acercontrol-setprofile", PROFILES[last_selected]])
        if result.cancelled or result.returncode != 0:
            return

        self._profile_panel.refresh()
        self._last_seen_profile_name = last_selected
        self.show_toast("Profile restored after resume")

    def _profile_notification_name(self, profile: Profile) -> str:
        if profile is Profile.CUSTOM:
            return "custom"
        return profile.display

    def _ensure_sensor_refresh(self) -> None:
        if self._last_seen_profile_name is None:
            self._last_seen_profile_name = self._profile_notification_name(read_profile())
        self._refresh_live_state()
        if self._sensor_source_id is None:
            self._sensor_source_id = GLib.timeout_add_seconds(2, self._refresh_live_state)

    def _refresh_live_state(self):
        reading = read_sensors()
        self._sensor_panel.update(reading)
        self._critical_notifier.update(reading.cpu_package_c)

        profile_name = self._profile_notification_name(read_profile())
        if self._last_seen_profile_name is None:
            self._last_seen_profile_name = profile_name
        elif profile_name != self._last_seen_profile_name:
            self.notify_profile_change(profile_name)
        return GLib.SOURCE_CONTINUE

    def _stop_sensor_refresh(self) -> None:
        if self._sensor_source_id is not None:
            GLib.source_remove(self._sensor_source_id)
            self._sensor_source_id = None

    def _on_close_request(self, *_args):
        self._stop_sensor_refresh()
        self._resume_controller.stop()
        return False

    def _on_disable_ppd_clicked(self, _banner_or_button) -> None:
        result = run_privileged(
            ["acercontrol-disable-ppd", "mask", "power-profiles-daemon.service"]
        )
        if result.cancelled:
            self._toast("Authentication cancelled.")
            return
        if result.returncode != 0:
            self._toast("Operation failed. See terminal for details.")
            return
        self._toast("power-profiles-daemon disabled.")
        # Re-probe → routing re-evaluates → banner self-removes
        self._route(probe())

    def _on_reload_acer_wmi_clicked(self, _button) -> None:
        result = run_privileged(["acercontrol-reload-acer-wmi"])
        if result.cancelled:
            self._toast("Authentication cancelled.")
            return
        if result.returncode != 0:
            self._toast("Operation failed. See terminal for details.")
            return
        self._toast("acer_wmi reloaded.")
        self._route(probe())
