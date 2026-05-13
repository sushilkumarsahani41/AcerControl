# Phase 2: Privilege Boundary + CLI — Context

**Gathered:** 2026-05-14
**Status:** Ready for research and planning
**Source:** `/gsd-discuss-phase 2` (4 gray areas, all answered)

<domain>
## Phase Boundary

Stand up the **privilege boundary end-to-end** with the CLI as its first consumer. Every privileged write goes through one of three real-binary wrappers at `/usr/libexec/acercontrol/`, each pinned to a named polkit action via `org.freedesktop.policykit.exec.path`. CLI ships full `status` / `get` / `set` / `list` / `temps` / `install` surface, bundled by `tools/bundle_cli.py` into a single stdlib-only file at `dist/acercontrol`. Phase 3 (GUI shell) and Phase 4 (profile control wired into GUI) consume this boundary unchanged — getting it right now is non-negotiable.

**In scope (12 requirements):** PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07.

**Out of scope (deferred to later phases):**
- GTK shell, Adwaita widgets, live sensor refresh in a window — Phase 3
- Toast/notification UX on profile change — Phase 4 + Phase 7
- Boot service `acer-performance.service` install/template — Phase 6 (this phase only ships the `manage-service` wrapper that Phase 6 will use)
- System tray indicator — Phase 7
- `.deb` packaging, polkit policy install paths in `debian/*.install` — Phase 8

</domain>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before acting.**

### Project-wide
- `./CLAUDE.md` — Project instructions (tech stack, sysfs paths, profile mapping, polkit policy XML skeleton, privilege escalation pattern, stack decisions table — **especially decisions #3 and #10**)
- `.planning/PROJECT.md` — Core value, constraints, tech stack, what-NOT-to-use table
- `.planning/REQUIREMENTS.md` — Authoritative definitions of PRIV-01..05 and CLI-01..07 (lines 19–30, 145–156)
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria (4 explicit checks), pitfall mitigations (P1, P14)

### Phase 1 carry-forward (consumed unchanged)
- `acercontrol/profiles.py` — `PROFILES` dict (5 user-name → kernel-value entries), `KERNEL_TO_UI` reverse map, `Profile` enum (6 members incl. `CUSTOM`), `kernel_to_profile()` helper
- `acercontrol/core.py` — `PROFILE_PATH`, `PROFILE_CHOICES_PATH`, `HWMON_BASE`, `PREDATOR_V4_PARAM`, `MODPROBE_D` constants; `read_profile()`, `read_sensors()`, `SensorReading` dataclass
- `acercontrol/features.py` — `probe()` returning `FeatureReport` with `.ok`, `.first_blocking_failure`; CLI `status` consumes this directly
- `acercontrol/sysfs.py` — `_read_or_none`, `find_hwmon`, `coretemp_max_package_temp`, `read_acer_sensors`
- `.planning/phases/01-foundation/01-RESEARCH.md` — §Security Domain (lines 1161–1186), §pyproject.toml skeleton (lines 921–959 — `[project.scripts]` slot)
- `.planning/phases/01-foundation/01-01-SUMMARY.md` — patterns established (defensive `_read_or_none`, `FeatureReport` for failure routing)
- `.planning/phases/01-foundation/01-VERIFICATION.md` — carry-forward note: downstream callers use `kernel_to_profile()` for unknown sysfs values

### External specs (read for accuracy, don't paraphrase from memory)
- freedesktop polkit `.policy` DTD — `org.freedesktop.policykit.exec.path` annotation semantics, `auth_admin_keep` lifetime
- systemd `pkexec(1)` man page — exit code 126 = auth cancelled, 127 = command not found, agent semantics

</canonical_refs>

<spec_lock>
## Locked Requirements (PRIV-01..05, CLI-01..07)

These come from `.planning/REQUIREMENTS.md` and the ROADMAP success criteria. The planner does **not** re-decide them.

| ID | Locked behavior |
|----|----------------|
| PRIV-01 | Privileged writes execute via real binary wrappers at `/usr/libexec/acercontrol/acercontrol-setprofile` (and siblings), never `pkexec bash -c '…'` |
| PRIV-02 | Polkit policy at `/usr/share/polkit-1/actions/org.acercontrol.policy` declares exactly three actions: `org.acercontrol.setprofile`, `org.acercontrol.set-boot-profile`, `org.acercontrol.manage-service`. Each action's `annotate org.freedesktop.policykit.exec.path` points at the matching wrapper binary. `allow_active = auth_admin_keep`; `allow_any` / `allow_inactive` = `auth_admin` (no `_keep`) |
| PRIV-03 | Polkit auth dialog shows the configured human-readable message string (e.g. "Authentication is required to change the Acer performance profile"), never the generic `org.freedesktop.policykit.exec` fallback ("Authentication is needed to run /usr/bin/bash") |
| PRIV-04 | `pkexec` exit 126 (auth cancelled) is handled idempotently — CLI prints "Authentication cancelled" and exits cleanly; second invocation within `auth_admin_keep` window does not re-prompt |
| PRIV-05 | When `$SSH_CONNECTION` is set in the environment, CLI escalates via `sudo` instead of `pkexec` (pkexec hangs over SSH waiting for a graphical agent) |
| CLI-01 | `acercontrol status` prints feature probe report + current profile (user-name) + available profiles + fan/temp summary |
| CLI-02 | `acercontrol get` prints user-facing names (`turbo` not `performance`); `acercontrol get --raw` prints the kernel value |
| CLI-03 | `acercontrol set <profile>` validates input against user-name mapping, escalates, writes through wrapper, reads back, exits non-zero on mismatch |
| CLI-04 | `acercontrol list` prints available user-facing profiles, marking the active one |
| CLI-05 | `acercontrol temps` prints CPU package temp + fan1/fan2 RPM + all hwmon temps |
| CLI-06 | `acercontrol install` prints install steps (or executes them when invoked as root) |
| CLI-07 | Zero non-stdlib runtime dependencies; bundled `dist/acercontrol` is a single stdlib-only file; CI guard fails the build if `import gi` leaks into any bundled source |

</spec_lock>

<decisions>
## Implementation Decisions (this discussion)

### Wrapper input validation policy → **Defense-in-depth**

Each wrapper at `/usr/libexec/acercontrol/*` **independently re-validates** its argv against an explicit allowlist before touching sysfs:

- `acercontrol-setprofile` and `acercontrol-set-boot-profile` accept only kernel values in `{"low-power", "quiet", "balanced", "balanced-performance", "performance"}` (the values of `acercontrol.profiles.PROFILES`). Any other argv → exit 64 (EX_USAGE), no sysfs write.
- `acercontrol-manage-service` accepts only `{"enable", "disable", "start", "stop"}` × the literal service name `acer-performance.service`. Any other action or service → exit 64.
- The CLI also validates upstream (faster UX feedback, no polkit prompt for typos), but the wrapper is the trust boundary and never assumes the CLI was the caller.

**Why:** The wrapper is what polkit invokes. A process that can `exec` `/usr/libexec/acercontrol/acercontrol-setprofile` directly (e.g. another local app with the right polkit action) MUST NOT be able to escape into arbitrary sysfs writes by passing creative argv. ~30 LOC per wrapper is a small premium for a security-relevant component.

### CLI output format → **Plain human-aligned default + `--json` opt-in**

Default output for `status`, `temps`, `get`, `list` is aligned human-readable text. A `--json` flag on each of these commands emits stable JSON with a documented schema. The Phase 3 GUI primarily imports `acercontrol.core` directly (same process, same package), but `--json` exists for scripting users AND as the test-suite parsing format on Linux runners.

**Locked default JSON shape (planner formalizes exact schema; this is the contract):**
- `acercontrol get --json` → `{"profile": "turbo", "kernel_value": "performance"}`
- `acercontrol temps --json` → `{"cpu_package_c": 55.0, "fan1_rpm": 6976, "fan2_rpm": 7142, "acer_temp1_c": 58.0, "acer_temp2_c": 53.0, "acer_temp3_c": null}` (null when the sysfs path is missing)
- `acercontrol list --json` → `{"profiles": ["eco", "quiet", "balanced", "performance", "turbo"], "active": "turbo"}`
- `acercontrol status --json` → `{"probe": {<FeatureReport.checks as list of dicts>, "ok": bool, "first_blocking_failure": {…}|null}, "profile": {…}, "list": [...], "temps": {…}}`

JSON is **append-only**: planner MUST NOT remove keys in future versions, only add. This is the GUI/scripting contract.

### `acercontrol install` non-root behavior → **Print + exit 0**

When invoked by a non-root user, `acercontrol install` prints the install steps (modprobe.d snippet, `systemctl enable acer-performance.service`, `update-initramfs -u`, optional `.deb` install command) and **exits 0**. Printing the instructions IS the deliverable when not root. Composes cleanly with `acercontrol install | sudo bash` for a one-shot.

When invoked as root (uid 0), it executes the same steps directly.

**Not chosen:** exit 1 (surprising for an interactive user who got useful output), interactive sudo prompt (scope creep, complicates the CLI testability story).

### CI / dev-machine testability → **`--dry-run` flag on every privileged CLI command**

Every CLI command that escalates (`set`, `install` in its root path) accepts a `--dry-run` flag. With `--dry-run`:
- Input is validated as in the normal path.
- The wrapper path that **would** be invoked, the resolved kernel value, the elevation method (`pkexec` or `sudo` based on `$SSH_CONNECTION`), and the would-be argv are printed.
- No subprocess elevation happens.
- Exit code is 0 (input valid) or 64 (input invalid).

`--dry-run` composes with `--json` (emits the same fields as a JSON object). The Phase 2 smoke runner exercises every CLI command via `--dry-run` on macOS, Linux without `acer_wmi`, and the PHN16-72 dev machine — so the same smoke runner runs in CI and locally.

**Not chosen:** env-var `ACERCONTROL_PRIVILEGED_RUNNER` test seam (hidden side-channel, surprise factor); skip-on-non-Linux (slower feedback loop, no CLI surface coverage outside the dev laptop).

### Claude's discretion (derived; planner does not re-ask)

- **Wrapper filenames:** `acercontrol-setprofile`, `acercontrol-set-boot-profile`, `acercontrol-manage-service` — match the action-ID suffixes from PRIV-02 (`setprofile`, `set-boot-profile`, `manage-service`).
- **Wrapper language:** Python — same stack as Phase 1 and the CLI, single source of truth for the `PROFILES` allowlist (wrapper imports `acercontrol.profiles.PROFILES` or duplicates the allowlist as a literal; planner picks whichever passes the trust-boundary review). Wrappers MUST remain stdlib-only and gi-free.
- **CLI module structure:** `acercontrol/cli.py` (entry point `main()`), `acercontrol/privilege.py` (escalation helper that picks `pkexec`/`sudo` and handles exit 126). `[project.scripts]` slot in `pyproject.toml` wires `acercontrol = "acercontrol.cli:main"`.
- **Bundler strategy:** stdlib-only concatenation by `tools/bundle_cli.py` (locked in CLAUDE.md stack decisions). Output: `dist/acercontrol` — a single executable Python file with `#!/usr/bin/env python3` shebang, `chmod +x`, no installer needed.
- **`tools/verify_no_gtk.py`:** mentioned in ROADMAP success criterion 4. Planner produces this; scope = grep-based gate that fails build if `^import gi` or `^from gi` appears in any bundled source.
- **Boot service that `manage-service` controls:** the literal `acer-performance.service` (CLAUDE.md, `install.sh` template). Phase 6 installs the actual unit file; Phase 2 ships only the wrapper that will be invoked once Phase 6 exists.
- **`auth_admin_keep` second-invocation test:** Phase 2 smoke-tests this on Linux only; manual UAT on PHN16-72 confirms the actual polkit dialog text.

</decisions>

<specifics>
## Specific References

- ROADMAP success criterion 1 ("Authentication is required to change the Acer performance profile") is the **literal message string** for the `org.acercontrol.setprofile` action's `message` element in `org.acercontrol.policy`. Planner uses this verbatim.
- CLAUDE.md "Polkit policy" section provides the XML structure (action element, allow_active/allow_inactive/allow_any, message, description). Planner copies the structure but replaces the placeholder action ID with the three real ones from PRIV-02.
- Phase 1 SUMMARY.md flags one open question: "does `acer_wmi predator_v4=1` preserve `platform_profile` across S3?" — out of scope for Phase 2 (belongs to Phase 6 / Phase 7 logind hook research).

</specifics>

<deferred>
## Deferred Ideas

- **`acercontrol install --interactive`** prompting `Run these now via sudo? [y/N]` — scope creep for v1. Re-evaluate after v1 if users ask for it.
- **`acercontrol set --no-verify`** that skips the read-back step in CLI-03 — possibly useful for benchmarking, but currently unmotivated. Defer.
- **`--quiet` / `-q` global flag** suppressing all output except errors — convenient for scripts; deferable, since `--json | jq .field` covers most scripting needs.
- **Per-action polkit `.rules` overlay** (e.g. require `auth_self` not `auth_admin` on `setprofile` for users in a specific group) — sysadmin-level customization, not in v1 scope. Phase 8 packaging may add a sample `.rules` snippet in docs.
- **Shell completion for `acercontrol`** (bash/zsh/fish) — nice-to-have, scope creep for Phase 2. Likely Phase 8 (packaging).

</deferred>

---

*Phase: 02-privilege-boundary-cli*
*Context gathered: 2026-05-14 via `/gsd-discuss-phase 2`*
*Next: `/gsd-plan-phase 2` to research, plan, and verify.*
