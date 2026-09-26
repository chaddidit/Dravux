# Portability

Dravux is built so the **contracts and validators stay OS-agnostic**. Host adapters and shell
installers may differ by platform; the meaning of a report must not.

## Support matrix (honest)

| Layer | macOS | Linux | Windows |
|---|---|---|---|
| Python validators (`dravux_contract.py`, `dravux_run.py`) | Supported | Supported | Supported in CI (stdlib only) |
| Offline test suite | Supported | Supported (CI) | Supported in CI |
| Release verifier (`verify-release.sh`) | Supported | Supported (CI) | Supported in CI via Bash |
| Plain installers (`install.sh`, `verify-install.sh`) | Supported | Expected | Not a native shell path yet |
| Claude / Codex / ChatGPT skill install via published ZIPs | Documented | Documented | Documented (host app dependent) |
| Native `cmd.exe` / PowerShell installer scripts | — | — | Not shipped |

"Supported in CI" means GitHub Actions runs the offline suite on that OS so a macOS-only maintainer
can still see Windows failures. It does **not** mean every documented click-path was manually
exercised on a Windows desktop.

## Design rules (keep these)

1. **Validators stay pure Python stdlib.** No POSIX-only calls in the contract or run validators
   except carefully gated filesystem helpers already used for audit-output safety
   (`O_NOFOLLOW` / `dir_fd` when available).
2. **Paths in contracts are strings, not host paths.** Report and run JSON must not require a
   particular drive letter or separator to validate.
3. **Shell is an adapter.** `install.sh` / `verify-*.sh` are the macOS/Linux operator path. A
   future Windows-native installer must call the same Python entry points and preserve refuse-overwrite,
   symlink, and mode checks — not invent a second honesty model.
4. **Demos and fixtures are portable text.** HTML/JSON fixtures must not embed maintainer home
   directories or OS-specific absolutes (already enforced by release verification).

## Windows without a Windows laptop

Use CI:

- Push to a branch and read the `windows-latest` job.
- Reproduce a failure locally only when needed (VM, cloud runner, or a friend's machine).

When adding Windows-sensitive behavior (paths, modes, reserved device names, line endings):

1. Prefer a **unit test that encodes the Windows rule** and runs on every OS (see archive reserved-name
   checks in `scripts/verify_distribution.py` and their tests).
2. Add or extend the **Windows CI** job if the bug can only appear on a real Windows filesystem.
3. Do not claim native PowerShell install support until those scripts exist and the Windows job
   exercises them.

## What is intentionally out of scope here

- A standalone GUI or browser extension (separate product layer; same contracts).
- Claiming that installing the skill grants a browser, network, or screen reader on any OS.
- Weakening symlink / mode / refuse-overwrite checks to "make Windows easier."

## Related docs

- [SECURITY.md](../SECURITY.md) — integrity gate, residual risks, vulnerability reporting
- [docs/capabilities.md](capabilities.md) — what each assistant surface can actually obtain
- [START_HERE.md](../START_HERE.md) — human install routes
