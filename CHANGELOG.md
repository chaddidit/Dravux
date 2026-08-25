# Changelog

## 1.0.2 — 2026-07-28

- Added the Dravux project website and a public GitHub Issues route for bugs, documentation problems, and feature requests, with a warning not to disclose private or sensitive information publicly.
- Replaced private workspace taxonomy in the privacy regression fixture with generic synthetic markers and removed an internal development-only reference from the public README.
- Refreshed active fixture tooling/provenance labels to Dravux 1.0.2 so current contract fixtures no longer present themselves as 1.0.1 output; historical 1.0.1 changelog entries remain unchanged.
- Migrated the report contract from `0.1.0` to `0.2.0` and the operational run contract from `1.1.0` to `1.2.0`; package version `1.0.2` and preflight contract `1.0.0` remain unchanged. Live fixtures, templates, schemas, tools, and tests use only the current contracts, while explicit unsupported-version fixtures preserve rejection coverage rather than legacy acceptance.
- Added the required `execution` object recording whether the audit itself completed, which stage failed, and why. A page that was acquired successfully but whose audit then failed must report an automated `ERROR`, a final `INCOMPLETE`, and a structured `EXECUTION_FAILED` error. No incomplete execution can coexist with an automated `PASS` or a final `VERIFIED PASS`.
- Bound each `MANUAL_OBSERVATION` to an exact, case-sensitive `manual_check_id`; the check must be declared and completed, every completed check needs an observation, and free-text matching no longer establishes the relationship.
- Made unsupported preflight deterministic, narrowed genuine `NOT APPLICABLE` to completed supported-target runs, required report `PASS` to have no errors, distinguished all `ERROR` receipt meanings, and required screenshot capability for `RENDERED_BROWSER`.
- Narrowed `CONTRACT_ONLY` runs to structure-only `PASS | INCOMPLETE` with no findings or errors and a receipt that says only the contract structure was validated; required `selected_mode` to equal the weaker of the requested mode and the demonstrated acquisition ceiling (an acknowledgement accepts a lower ceiling and never authorizes a voluntarily weaker mode); required at least one `SCREENSHOT` evidence item for a completed `RENDERED_BROWSER` run (a browser acquisition that failed is not asked for a picture it cannot have); restricted `CONTRACT_ONLY` runs and failed acquisitions to `TOOL_OUTPUT`/`COMMAND_OUTPUT` diagnostic evidence with no findings, so a report can no longer cite `SOURCE`, `DOM`, `SCREENSHOT`, or other target evidence for a target that was never acquired; gave every valid `VERIFIED FAIL` receipt its own meaning (automated `FAIL`, automated `PASS` overridden by a bound manual failure, automated `ERROR` with a bound manual failure); shipped the bounded `fixtures/operational/decorative-spacer.svg` asset that the genuine `NOT APPLICABLE` fixture records; and rejected archive member and inventory names that collide after combined Unicode NFC normalization and case folding.
- Added strict bounded JSON ingress for file and stdin input, including byte, UTF-8, nesting, container, aggregate-item, string/key, numeric-token, and structural-token limits while retaining duplicate-key and non-finite-number rejection.
- Hardened release construction and verification with an authoritative shared inventory, duplicate manifest/attestation-path rejection, pre-CRC ZIP metadata and resource budgets, safe archive-name normalization and collision checks, and one-line escaped diagnostics for malformed or hostile input.
- Validated every recorded website redirect hop against literal special-address and metadata-host rules. Acquisition guidance now requires DNS resolution before the initial request and every redirect hop, fails closed unless every A/AAAA address is global, and states explicitly that the offline validator performs no DNS and cannot eliminate DNS rebinding.
- Hardened personal-path canonicalization, installer and installed-copy parent traversal, and audit-output directory creation against symlink/alias redirection without changing modes on pre-existing directories.
- Pinned both GitHub workflows to immutable official action commits with read-only permissions, disabled checkout credentials, bounded job time, bytecode/UTF-8 guards, and explicit Ubuntu Python 3.8, Ubuntu Python 3.13, and macOS Python 3.13 root coverage.
- Put archive digest checks before extraction, upload, installation, or execution throughout the operator guides, while stating that same-channel checksums and internal records prove consistency only and that this release has no cryptographic publisher signature.
- Renamed the builder's unsigned console label from `ATTESTED:` to `RECORDED:`; the internal record filename remains stable.
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
- Declared the shipped-file inventory explicitly in the release verifier. The manifest is regenerated from the tree at build time, so a file deleted or added before a build used to ship unnoticed; verification now fails closed on any difference from the declared list.
- Reported a missing required release file and invalid JSON anywhere in the tree (including the manifest and attestation) as plain `FAIL:` lines instead of Python tracebacks.
- Rejected symlink and special-file members during archive verification, alongside the existing unsafe-path and operating-system-metadata checks.
- Pointed the offline demo runbook at a disposable copy of the demo page so the documented demo no longer rewrites a manifest-verified file.
- Moved the canonical shipped skill from `skill/dravux/` to `plugins/dravux/skills/dravux/` inside the plugin layout, and added `install.sh`, `verify-install.sh`, and `verify-release.sh`; the 1.0.1 path `skill/dravux/scripts/...` no longer exists.
- Quoted attacker-authored key names and list items in validator diagnostics as escaped single-line literals, so a hostile file can no longer print a forged verdict line or terminal escape through the validator's own error output.
- Applied the control-character exclusion to every free-text field of the published preflight and run schemas and to `scope.applicability_reason`, matching what the bundled validator already enforces.
- Stopped the repo-level entry points (`scripts/validate_report.py`, `scripts/audit_demo_html.py`, `scripts/run_tests.py`, the verifier's archive rebuild) from writing `__pycache__` into the verified tree on stock CPython.
- Made `install.sh` set the installed modes itself (`0755` directories, `0644` files, independent of the caller's umask, including the top-level folder) and made `verify-install.sh` fail on group- or world-writable entries and on executable-bit drift.
- Ran the shell entry points' Python version probe with `-B`, so a relative `HOME` can no longer make Apple's Python write a bytecode cache into the directory `verify-release.sh`, `install.sh`, or `verify-install.sh` was run from.
- Required an unsuccessful acquisition to carry no content hash or HTTP status, and a final location that differs from the requested one to come with a recorded redirect chain.
- Bounded RFC 3339 offsets in the validator itself (`±[00-23]:[00-59]`) instead of inheriting the interpreter's behaviour.
- Required `manual_checks_completed` to be non-empty for `VERIFIED PASS` in the published report schema, matching the validator.
- Printed the requested mode in the run receipt and reported the limitation acknowledgement as "not required" when the requested mode was available, instead of echoing an idle flag as "accepted".
- Turned two `skipTest` guards into hard assertions, asserted the published execution invariants structurally, and declared the expected test count so a deleted test module or method can no longer pass silently; fixtures are now judged through the strict loader, and nested duplicate keys are tested.

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
