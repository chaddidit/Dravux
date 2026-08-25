# Dravux Quickstart

This page is the technical quickstart. If you are not working in a terminal, start with
[START_HERE.md](../START_HERE.md) instead — it covers the upload and desktop-app routes.

## Artifact integrity gate

Before extracting, uploading, installing, or running a downloaded archive, keep it unopened and run
`shasum -a 256 <archive-name>`. Compare that digest with the exact archive entry in the accompanying
`SHA256SUMS.txt`; continue only when it matches. A same-channel checksum, the embedded manifest, and
the internal release record detect corruption or inconsistency only and do not authenticate the
publisher. Dravux 1.0.2 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.**

After the digest matches, extract the engineering archive and run `sh verify-release.sh` before any
installer, upload, or Dravux execution. A source checkout intentionally contains no installer ZIPs;
run the verifier on the checkout before local use, or obtain the separately published archive needed
by the upload route.

## Quick self-test (about 10 seconds)

From the extracted release root, run:

```bash
sh verify-release.sh
```

This is fully offline. It needs no credentials, no network access, and no package installs. Exit code `0` is success, and the expected final line is:

```
VERIFIED: Dravux 1.0.2 release tree passed all offline checks
```

Any other exit code means the release tree did not verify. Do not treat the package as usable until this passes.

## 1. Define and preflight the audit

Record the product surface, target, state, input type, requested evidence mode, included/excluded scope, required manual checks, and whether repair is authorized. Copy `plugins/dravux/skills/dravux/assets/preflight-template.json`, fill in only capabilities actually present, and run:

```bash
python3 -B plugins/dravux/skills/dravux/scripts/dravux_run.py preflight path/to/preflight.json
```

Continue only after `READY`. `LIMITATION_ACK_REQUIRED` means the user must explicitly accept the reduced mode. `UNSUPPORTED` means the current surface cannot establish a Dravux result.

## 2. Use the skill

Install or reference `plugins/dravux/skills/dravux/` in the location supported by your agent. Use the matching note under `adapters/`.

## 3. Choose where output goes

Audit artifacts never belong inside the skill, this package, or an extracted release; writing there
makes the manifest and internal consistency checks fail. Ask for the correct directory instead:

```bash
python3 -B <skill-root>/scripts/dravux_run.py output-dir
```

The last printed line is the absolute path to use — a `dravux-audits` directory outside every
protected tree. Add `--audit-id <slug>` to separate runs, and `--strict` to refuse rather than
redirect when the starting directory is inside a protected tree.

## 4. Create a report

Copy `plugins/dravux/skills/dravux/assets/report-template.json` into that output directory. Do not put private local paths in public reports.

## 5. Validate the report

```bash
python3 -B scripts/validate_report.py path/to/report.json
```

For a response-only report, resolve the installed skill root and stream the complete JSON to its bundled validator instead of saving it in the project:

```bash
python3 -B <skill-root>/scripts/dravux_contract.py -
```

Do not present an in-chat or live-URL summary as a Dravux result until the validator exits `0`.

Exit codes:

- `0`: contract valid
- `1`: JSON loaded but violates the Dravux contract
- `2`: file or JSON loading error

## 6. Validate the operational run

For an audit, copy `plugins/dravux/skills/dravux/assets/run-envelope-template.json` and add the completed preflight, acquisition receipt, and report. Then run:

```bash
python3 -B plugins/dravux/skills/dravux/scripts/dravux_run.py validate path/to/run-envelope.json
```

Operational exit `0` emits the required run receipt. A bare report is not an established audit run. If either validator cannot execute, return `UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

## 7. Finish honestly

Place the run receipt first, then report findings, evidence, tests, errors, and manual checks remaining. Automated `PASS` plus pending manual checks is `INCOMPLETE`.
