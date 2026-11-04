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
- The GitHub-tag route (`npx --yes github:chaddidit/Dravux#v1.0.3`) is published. npm registry
  publication is separate and has not happened; `npx dravux@1.0.3` will not work until it does.
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

## Deferred to 1.0.4

- Installer: check setuid bits and ownership; support 0775 `~/.claude`; address the glibc 2.28 requirement for `renameat2`.
- Validator: make preflight errors in validate more informative; decide how to handle DNS names resolving to internal IPs, which requires network resolution.
- Packaging: include `LICENSE` and `THIRD_PARTY_NOTICES.md` in the canonical skill folder, so the
  standalone Claude ZIP and plain installed skill copies keep them. Add archive and installed-copy
  regression checks.
- Packaging: make the slim npm package's documentation links and commands usable without the
  engineering tree.

## Next

4. **Front-language pass** — Keep honesty; shorten integrity essays on the front door (done for
   the main guides via `SECURITY.md`); continue plain-language edits in adapters and CHANGELOG
   Highlights vs Engineering.
5. **CLI reference** — One page for `dravux_run.py` / `dravux_contract.py` commands and exit codes.
6. **Windows-native operator path** — Optional `cmd`/PowerShell wrappers that call the same Python
   entry points; land only with Windows CI coverage (`docs/portability.md`).

## Not doing (for now)

- Claiming publisher authenticity without a signature.
- A SaaS status page or “WCAG certified” badge.
- Growing the demo HTML auditor into a full accessibility engine.
- A GUI or browser extension as part of this package.
