# Portability

Dravux is built so the **contracts and validators stay OS-agnostic**. Host adapters and shell
installers may differ by platform; the meaning of a report must not.

## Support matrix (honest)

| Layer | macOS | Linux | Windows |
|---|---|---|---|
| Python contract, preflight, and run validation | Supported | Supported | Core CI job configured; require a passing run |
| Full offline test suite | Supported | Supported (CI) | Not supported |
| Release verifier (`verify-release.sh`) | Supported | Supported (CI) | Not supported |
| Plain installers (`install.sh`, `verify-install.sh`) | Supported | Supported | Not a native shell path yet |
| Safe `output-dir` filesystem helper | Supported | Supported | Refused before creation |
| Claude / Codex / ChatGPT skill install via published ZIPs | Documented | Documented | Documented (host app dependent) |
| Native `cmd.exe` / PowerShell installer scripts | — | — | Not shipped |

The Windows job runs `tests.test_contract`, `OperationalContractTests`, and
`ExecutionFailureContractTests`. It does not test shell installers, POSIX modes, safe output-directory
creation, or full release packaging. A configured job is not evidence of a passing run; inspect the
checks on the exact release commit. Host-app installation routes still require manual verification.

The installer uses atomic exclusive rename on Linux and macOS. If the OS or filesystem does not
support that operation, installation fails safely; it never falls back to merging directories.

## Linux exclusive rename

When libc provides `renameat2`, the installer uses it with `RENAME_NOREPLACE`.
If the wrapper is missing (including glibc before 2.28), it uses `libc.syscall` directly:

| Architecture | System call number |
|---|---|
| x86_64 | 316 |
| aarch64 | 276 |
| armv7 | 382 |
| i386 (also reported as i686 or i586) | 353 |
| ppc64le | 357 |
| s390x | 347 |
| riscv64 | 276 |

Any other architecture, `ENOSYS`, `EINVAL`, or inability to run the call causes refusal with
nothing installed. There is no fallback to a rename that can replace a destination.
For owner/group permission refusals, including macOS `staff`, see
[Troubleshooting](troubleshooting.md#installer-refused-an-owner-or-writable-parent).
Windows-native installation remains open as [#8](https://github.com/chaddidit/Dravux/issues/8).

## Design rules (keep these)

1. **Validators stay pure Python stdlib.** No POSIX-only calls in the contract or run validators
   except carefully gated filesystem helpers already used for audit-output safety
   (`O_NOFOLLOW` / `dir_fd` required for `output-dir`; unavailable support is refused).
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
