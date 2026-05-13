# Phase 2: Privilege Boundary + CLI — Discussion Log

**Session:** 2026-05-14
**Mode:** `/gsd-discuss-phase 2` (default, no flags)
**Outcome:** 4 gray areas selected and answered; CONTEXT.md written.

This log is for human audit/retrospective. Downstream agents (researcher, planner, executor) read `02-CONTEXT.md`, not this file.

---

## Pre-discussion analysis

**Already locked by upstream artifacts (not re-asked):**
- Three wrappers + three named polkit actions (PRIV-02 names them exactly: `setprofile`, `set-boot-profile`, `manage-service`)
- `pkexec` primary, `sudo` fallback when `$SSH_CONNECTION` set (PRIV-05)
- Real-binary wrapper, never `pkexec bash -c` (PRIV-01)
- `auth_admin_keep` on `allow_active` (PRIV-02 / CLAUDE.md)
- Exit 126 handled idempotently (PRIV-04)
- Profile name mapping (Phase 1 `acercontrol.profiles.PROFILES`)
- Bundler is stdlib-only concatenation → `dist/acercontrol` (CLI-07 + CLAUDE.md)
- `install` prints OR executes if root (CLI-06)
- Pitfalls P1, P14 explicitly in scope (ROADMAP)

**Gray areas presented to user (multiSelect):**
1. Wrapper input validation policy ✓ selected
2. CLI output formats (`status`, `temps`, `get`) ✓ selected
3. `acercontrol install` non-root behavior ✓ selected
4. CI / non-Linux dev-machine testability ✓ selected

User selected all four.

---

## Q1 — Wrapper input validation policy

**Question:** The wrapper is the trust boundary — should each wrapper re-validate its argv independently, or trust the CLI to have validated?

**Options presented:**
- (a) Defense-in-depth (Recommended) — each wrapper re-validates against allowlist; CLI also validates
- (b) CLI validates, wrapper trusts — single validation path
- (c) Wrapper validates, CLI assumes

**User selection:** (a) Defense-in-depth (Recommended)

**Captured decision:** Each wrapper at `/usr/libexec/acercontrol/*` independently re-validates argv against an explicit allowlist (kernel profile values for the two profile-setting wrappers; `{enable,disable,start,stop} × acer-performance.service` for `manage-service`). CLI validates upstream for UX, wrapper is the trust boundary.

**Why this matters for the planner:** ~30 LOC per wrapper for the allowlist check; cannot import `acercontrol.profiles` from `/usr/libexec/` because system Python won't have the package on `sys.path` — planner must decide between (i) duplicating the allowlist as a literal in each wrapper and adding a parity grep gate in tests, or (ii) installing `acercontrol` to system site-packages. The discussion did not nail this — flagged as planner-discretion in CONTEXT.

---

## Q2 — CLI output format

**Question:** Default output format for `status`, `temps`, `get`, `list` (Phase 3 GUI will consume `temps` programmatically).

**Options presented:**
- (a) Plain human-aligned default + `--json` flag (Recommended)
- (b) Plain only, defer JSON to v1.1 (GUI imports Python API directly)
- (c) Always JSON + `--pretty` flag

**User selection:** (a) Plain human-aligned default + `--json` opt-in

**Captured decision:** Default is aligned human text. `--json` flag emits stable schema. JSON is append-only across versions.

**Locked JSON shape (captured in CONTEXT.md `<decisions>`):**
- `get --json` → `{"profile": str, "kernel_value": str}`
- `temps --json` → `{"cpu_package_c": float|null, "fan1_rpm": int|null, "fan2_rpm": int|null, "acer_temp1_c": float|null, "acer_temp2_c": float|null, "acer_temp3_c": float|null}`
- `list --json` → `{"profiles": [str], "active": str}`
- `status --json` → bundles probe + profile + list + temps

---

## Q3 — `acercontrol install` non-root behavior

**Question:** CLI-06 says "prints (or executes when run as root)". What is the non-root exit code?

**Options presented:**
- (a) Print + exit 0 (Recommended)
- (b) Print + exit 1
- (c) Print + offer interactive sudo prompt

**User selection:** (a) Print + exit 0

**Captured decision:** Non-root invocation prints the install steps and exits 0. Composes with `acercontrol install | sudo bash` for one-shot. Root invocation (uid 0) executes the same steps directly.

**Rationale captured:** printing IS the deliverable when not root; exit 1 would be surprising for an interactive user who got useful output; interactive sudo prompt is scope creep.

---

## Q4 — CI / non-Linux dev-machine testability

**Question:** How does Phase 2 exercise wrapper + pkexec paths on macOS / CI without `/sys` or polkit?

**Options presented:**
- (a) `--dry-run` flag on every privileged CLI command (Recommended)
- (b) Env-var test seam `ACERCONTROL_PRIVILEGED_RUNNER`
- (c) Skip wrapper tests on non-Linux — PHN16-72 UAT only
- (d) Combine: `--dry-run` + skip-on-non-Linux for wrapper-side tests

**User selection:** (a) `--dry-run` flag on every privileged CLI command

**Captured decision:** Every escalating CLI command accepts `--dry-run`. With `--dry-run` set, input is validated, would-be wrapper path + resolved kernel value + elevation method + argv are printed, no subprocess elevation. Exit 0 (valid) or 64 (invalid). Composes with `--json`. Phase 2 smoke runner uses `--dry-run` to exercise the full CLI surface on macOS and CI.

**Wrapper-side tests:** The actual `/usr/libexec/acercontrol/*` binaries' argv validation is exercised by direct invocation on the dev machine and CI (no elevation needed for the validation path itself — only the sysfs write needs root, and `--dry-run` covers that case from the CLI side). Manual UAT on PHN16-72 confirms the polkit dialog message string.

---

## Deferred ideas (not in scope for v1)

Captured in CONTEXT.md `<deferred>`:
- `acercontrol install --interactive` prompting for sudo
- `acercontrol set --no-verify` skipping the read-back
- Global `--quiet` / `-q` flag
- Per-action polkit `.rules` overlay (sysadmin customization)
- Shell completion (bash/zsh/fish)

---

## Scope-creep moments

None. User answered each question within its scope; no scope-expanding suggestions surfaced during the discussion.

---

## Next steps shown to user

`/gsd-plan-phase 2` — research → plan → verify, consuming this CONTEXT.md.
