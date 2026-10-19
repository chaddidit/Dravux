# Tracked work (seed issues)

These are the backlog items agreed after the 1.0.2 review. Open each as a GitHub Issue
(use the templates under `.github/ISSUE_TEMPLATE/`) so progress is visible. Do not treat this
file as a certification roadmap.

Opened issues:

- [#4](https://github.com/chaddidit/Dravux/issues/4) Preflight URL policy parity
- [#5](https://github.com/chaddidit/Dravux/issues/5) Receipt C1/bidi display hardening
- [#6](https://github.com/chaddidit/Dravux/issues/6) install.sh staging scan
- [#7](https://github.com/chaddidit/Dravux/issues/7) CLI reference docs
- [#8](https://github.com/chaddidit/Dravux/issues/8) Windows-native operator path
- [#9](https://github.com/chaddidit/Dravux/issues/9) Publish GitHub Release artifacts

## Implemented in the release candidate, pending merge and publication

1. **#4 Preflight URL policy parity** uses acquisition's literal URL policy.
2. **#5 Receipt display hardening** escapes terminal controls and bidi formatting in text receipts;
   JSON remains the authoritative machine form.
3. **#6 Installer staging scan** rejects symlinks/special files before staged code runs. Source scans
   also reject special files; finalization atomically refuses an existing destination.
4. Independent review added regressions for repaired manual evidence, archive extraction conflicts,
   and unsupported output-directory platforms. These changes still require exact-commit CI and
   release-owner manual checks; this page does not mark a GitHub issue closed.

## Next

4. **Front-language pass** — Keep honesty; shorten integrity essays on the front door (done for
   the main guides via `SECURITY.md`); continue plain-language edits in adapters and CHANGELOG
   Highlights vs Engineering.
5. **CLI reference** — One page for `dravux_run.py` / `dravux_contract.py` commands and exit codes.
6. **Windows-native operator path** — Optional `cmd`/PowerShell wrappers that call the same Python
   entry points; land only with Windows CI coverage (`docs/portability.md`).
7. **GitHub Release artifacts** — Publish 1.0.2 (or next) with zips + `SHA256SUMS.txt` and short
   user-facing notes so download docs match reality.

## Not doing (for now)

- Claiming publisher authenticity without a signature.
- A SaaS status page or “WCAG certified” badge.
- Growing the demo HTML auditor into a full accessibility engine.
- A GUI or browser extension as part of this package.
