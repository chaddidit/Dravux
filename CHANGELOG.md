# Changelog

## 1.0.2 — 2026-10-30

- Added an optional dependency-free npx launcher for the existing installer and installed-copy verifier.

- Added an operational run-contract revision (`1.1.0`) with a required `execution` object recording whether the audit itself completed, which stage failed, and why. A page that was acquired successfully but whose audit then failed now has a legal, explicit envelope shape instead of no representation at all; it must report an automated `ERROR`, a final `INCOMPLETE`, and a structured `EXECUTION_FAILED` error. No incomplete execution can coexist with an automated `PASS` or a final `VERIFIED PASS`.
- Added a `dravux_run.py output-dir` subcommand that resolves where audit artifacts belong. Audit output is always written to a `dravux-audits` directory outside the installed skill, the source checkout, and any extracted release, so a verified tree stays verified. `--strict` refuses instead of redirecting; `--audit-id` separates runs.
- Added `START_HERE.md` and restructured `README.md` so a plain-language explanation and four clearly labelled routes come before any architecture, followed by a 60-second self-test, a first offline website test with expected outcomes, and troubleshooting organised by what the reader saw on screen.
- Documented that a `LIMITATION_ACK_REQUIRED` stop is a correct capability stop with a defined next action, not a failed audit.
- Added a top-level `INSTALLERS/` folder to the engineering archive: one folder per app, each with instructions and a ready-made archive injected at build time and byte-identical to the standalone download. `SHA256SUMS.txt` lists both so the match can be checked.
- Made the operating-system metadata policy explicit: release archives contain none at any depth, `Thumbs.db` and `desktop.ini` join the excluded set, loose copies in an extracted tree now produce a plain-language warning instead of a failure, and the same entries inside an archive are treated as tampering.
- Rejected control characters in contract string fields, closing a path that could forge lines in the run receipt.
- Rejected duplicate JSON keys when loading a report, so on-disk text can no longer disagree with the validated verdict.
- Required the baseline manual checks to be declared before `VERIFIED PASS`, closing a path where a report declaring no manual checks earned a verified pass from automation alone.
- Made release archives byte-reproducible regardless of the builder's umask.
- Stopped the test suite from rewriting `RELEASE_MANIFEST.json` as a side effect of running, and exercised the manifest-drift detector for real.
- Corrected the test suite so it passes in an ordinary git checkout, not only in an exported release tree.
- Removed the hard-pinned package-version literal from release verification; the installer and verifier now report the actual version.

## 1.0.1 — 2026-07-20

- Added a deterministic capability preflight and operational run contract without changing report contract 0.1.0.
- Required explicit acknowledgement before a website audit is reduced to converted text, raw source, or another lower evidence mode.
- Added acquisition receipts and a plain-language run receipt for every established audit.
- Added dedicated Claude custom-skill and pre-publication OpenAI plugin-source archives.
- Corrected cross-surface installation guidance: ordinary Chat attachments are context, not native installation.
- Bundled valid and hostile self-test fixtures so direct skill uploads can verify themselves without project files.
- Rejected hidden deterministic normative failures labeled automated `PASS` and unsupported manual-check completion.

## 1.0.0 — 2026-07-20

- First public portable release.
- Self-contained Agent Skill with bundled schemas and standard-library validator.
- Separate automated and verified verdict layers with explicit manual-review boundaries.
- Hostile, malformed, ambiguity, false-positive, and portability regression fixtures.
- Safe raw installation for Claude and Codex personal or project skill locations.
- Local plugin marketplace metadata for Claude and Codex.
- Offline release, installer, archive, privacy, and contract verification.
