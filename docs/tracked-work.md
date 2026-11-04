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

## Published in 1.0.3

Dravux 1.0.3 was published on November 3, 2026, after
[PR #12](https://github.com/chaddidit/Dravux/pull/12) merged into `main`.

- Release: [v1.0.3](https://github.com/chaddidit/Dravux/releases/tag/v1.0.3). The annotated tag
  points to commit `8166a35db883c77c88f55dc2d9f27caaf1ed34ff`. The tag is not signed.
- CI on that exact commit passed: [run 41725398661](https://github.com/chaddidit/Dravux/actions/runs/41725398661).
  Ubuntu with Python 3.8, Ubuntu with Python 3.13 and macOS with Python 3.13 each ran 264 tests with
  one expected platform skip. Windows with Python 3.13 ran the 93 portable-contract tests only; it does
  not run full release verification and does not establish native Windows installation support.
- CodeQL analysis on that commit passed: [run 41725367837](https://github.com/chaddidit/Dravux/actions/runs/41725367837).
  A successful analysis is not a statement that no vulnerabilities exist.
- All five release downloads were fetched back and checked. All seven entries in `SHA256SUMS.txt`
  matched, including the two embedded installer ZIPs and the release record. The embedded installer
  ZIPs are byte-identical to the standalone downloads. Every packaged source file matched the tagged
  commit's contents and executable modes, and the downloaded engineering release passed
  `sh verify-release.sh`.
- These checksums come from the same channel as the downloads. They establish consistency, not
  publisher identity. 1.0.3 has no cryptographic publisher signature, and publisher authenticity was
  not independently verified. Details: [SECURITY.md](../SECURITY.md).
- The GitHub-tag route (`npx --yes github:chaddidit/Dravux#v1.0.3`) and npm registry package
  (`npx --yes dravux@1.0.3`) are published. Registry publication was separate from the GitHub release.
- #9 covered publication of the release artifacts and short notes. Its completion does not mean the
  release-owner manual checks, any accessibility certification, or any other issue is complete.

The documentation packaged inside the 1.0.3 downloads is a historical snapshot of the tagged commit.
Later tracking and documentation corrections on `main` do not replace the release assets or move the
tag.

### Changes delivered in 1.0.3

1. **#4 Preflight URL policy parity** uses acquisition's literal URL policy.
2. **#5 Receipt display hardening** escapes terminal controls and bidi formatting in text receipts;
   JSON remains the authoritative machine form.
3. **#6 Installer staging scan** rejects symlinks/special files before staged code runs. Source scans
   also reject special files; finalization atomically refuses an existing destination.
4. Independent review added regressions for repaired manual evidence, archive extraction conflicts,
   and unsupported output-directory platforms. Exact-commit CI passed for the release; release-owner
   manual checks are still separate, and this page does not mark a GitHub issue closed.

## Published in 1.0.4

**Pending release verification.** This is the implementation checklist, not a publication receipt.
The integrator fills in the release URL, exact commit, CI runs, final test count, npm file count,
artifact/checksum read-back and issue closure facts after publication. The user-facing release
instructions use the published npm route `npx --yes dravux@1.0.4`; 1.0.3 is also on npm.
The GitHub-tag route is the alternative. No 1.0.4 publication or CI result is certified here.

Implemented scope to verify in the integrated release:

- **A1:** installer parent ownership checks; installed-copy ownership and setuid/setgid/sticky refusal.
- **A2:** tightly bounded 0775 exception for a user-owned primary group with no other listed member;
  macOS `staff` normally remains refused, with `chmod g-w <path>` guidance.
- **A3:** Linux direct `renameat2` syscall fallback when libc lacks the wrapper; safe refusal on
  unsupported architecture or syscall, never an overwriting rename.
- **B1:** actionable preflight diagnostics in `validate`: JSON path, expected and bounded found value.
- **B2:** escaped output-directory refusal/suggestion paths, including HOME-derived suggestions.
- **B3:** guarded-root markers checked with `lstat`, regardless of type or dangling symlink.
- **B4:** contract control/bidi rejection even alongside visible text; field/code-point diagnostics;
  ZWJ, ZWNJ and soft hyphen remain allowed.
- **C1:** canonical skill license/notices match root copies byte for byte.
- **C2:** license/notices accompany both ZIPs, npm and plain installs.
- **C3:** authoritative build/distribution inventories include the legal files, new tests and docs.
- **C4:** npm allow-list and tests match the real dry-run list; final file count pending integrator.
- **D1:** README front door at most 150 lines; full installation/reference and symptom-led help moved
  to [Install](install.md) and [Troubleshooting](troubleshooting.md), preserving factual detail.
- **D2:** npm-safe README/SECURITY links pinned to v1.0.4 for files absent from the slim package;
  engineering-only commands are identified.
- **D3:** npm-first 1.0.4 instructions, with the GitHub tag as the alternative and 1.0.3 publication retained.
- **D4:** integrity before use, app-based upload, unchanged unsigned-publisher disclosures.
- **D5 / [#7](https://github.com/chaddidit/Dravux/issues/7):** [CLI reference](cli-reference.md)
  covers both validators' commands, flags and exits, derived from code/help. Ready for issue closure
  after release; this document does not mark the issue closed itself.

The deferred list is removed: its implementation items are above, and DNS resolution is explicitly
under “Not doing” below. The 1.0.3 publication record remains historical evidence.

## Still open

- **[#8](https://github.com/chaddidit/Dravux/issues/8) Windows-native operator path:** optional
  `cmd`/PowerShell wrappers need real Windows CI coverage; no native installer is claimed
  ([Portability](portability.md)).
- Release-owner manual checks and exact-commit independent verification remain separate gates.

## Not doing (for now)

- **DNS-to-internal-IP validation:** permanently outside the offline validator because it requires
  network resolution. Literal URL checks cannot detect a hostname resolving to an internal address;
  acquisition tooling owns DNS and redirect safety ([SECURITY.md](../SECURITY.md)).

- Claiming publisher authenticity without a signature.
- A SaaS status page or “WCAG certified” badge.
- Growing the demo HTML auditor into a full accessibility engine.
- A GUI or browser extension as part of this package.
