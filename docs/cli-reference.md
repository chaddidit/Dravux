# CLI reference

Dravux 1.0.4 has two bundled Python entry points. This reference is derived from their
`build_parser()` / `main()` code and `--help` output. Both use Python 3.8+ and the standard library;
validation is offline. This page resolves the documentation work in
[#7](https://github.com/chaddidit/Dravux/issues/7); issue closure is a release-owner action.

## Artifact integrity gate

Before extracting, uploading, installing, or running a downloaded archive, keep it unopened,
calculate `shasum -a 256 <archive-name>`, and compare its exact entry in `SHA256SUMS.txt`.
Continue only when it matches. Same-channel checksums establish consistency, not publisher identity.
Dravux 1.0.4 has no cryptographic publisher signature.
**Publisher authenticity was not independently verified.** See [SECURITY.md](../SECURITY.md).
From an extracted engineering ZIP or source checkout, run its `sh verify-release.sh` before use;
that file is absent from the npm launcher.

## Locate the scripts

Replace `<skill-root>` below with the installed `dravux` skill folder. In an engineering ZIP or
source checkout it is `plugins/dravux/skills/dravux`; in a plain project install it is
`.claude/skills/dravux` or `.agents/skills/dravux`. The npm package includes the same bundled scripts.
Do not write reports inside the installed skill, checkout, or release tree.

## `dravux_contract.py`: validate a report

```text
python3 -B <skill-root>/scripts/dravux_contract.py [-h] [--json] report
```

There are no subcommands. `report` is a required path to report JSON; `-` reads the complete JSON
from standard input. `--json` emits a machine-readable validation summary. `-h` / `--help` prints
help and exits without validation.

```bash
python3 -B <skill-root>/scripts/dravux_contract.py /path/to/report.json
python3 -B <skill-root>/scripts/dravux_contract.py --json - < /path/to/report.json
```

| Exit | Meaning |
|---|---|
| `0` | Report satisfies the contract. This alone does not establish an operational run or certify a target. |
| `1` | JSON loaded but violates the report contract, including hostile structures safely rejected during validation. |
| `2` | File/JSON loading failure, or command-line usage error. |

Successful text output is `VALID Dravux report: <audit_id> | <automated_result> | <final_status>`.
Invalid-report and load diagnostics go to standard error. With `--json`, summaries go to standard
output and contain `valid` and `errors`; loaded-report summaries also contain `audit_id`,
`automated_result` and `final_status`. Load-error JSON includes `exit_code: 2`; loaded-report JSON
has no `exit_code` field, so always read the process exit status.

## `dravux_run.py`: preflight, validate, or place output

```text
python3 -B <skill-root>/scripts/dravux_run.py [-h] {preflight,validate,output-dir} ...
python3 -B <skill-root>/scripts/dravux_run.py preflight [-h] [--json] input
python3 -B <skill-root>/scripts/dravux_run.py validate [-h] [--json] input
python3 -B <skill-root>/scripts/dravux_run.py output-dir [-h] [--base BASE] [--audit-id AUDIT_ID] [--strict] [--json]
```

A subcommand is required. `-h` / `--help` is available at the top level and for each subcommand;
help exits `0`, while parser usage errors exit `2`. Put subcommand flags after the subcommand.
There is no separate receipt command: `validate` emits the receipt only after a valid run.

### `preflight`

`input` is a required preflight JSON path; `-` reads standard input. `--json` emits the decision
object instead of the text preflight summary. It validates the declared session and runs the bundled
validator self-test; it does not acquire or audit a target.

```bash
python3 -B <skill-root>/scripts/dravux_run.py preflight /path/to/preflight.json
python3 -B <skill-root>/scripts/dravux_run.py preflight --json - < /path/to/preflight.json
```

| Exit | Status | Meaning |
|---|---|---|
| `0` | `READY` | Valid preflight, bundled validator available, no unacknowledged evidence reduction. |
| `1` | `INVALID` | Contract violation, including a selected evidence mode beyond the declared capability ceiling. |
| `2` | `LOAD_ERROR` | File/JSON loading failure; parser usage errors also exit `2`. |
| `3` | `LIMITATION_ACK_REQUIRED` | Selected mode is weaker than requested and the user has not explicitly accepted it. Stop before acquisition. |
| `4` | `UNSUPPORTED` | Unsupported input, missing code execution/bundled files/validator capability, or failed bundled self-test. No audit result. |

Text prints `DRAVUX PREFLIGHT: <status>`, the validator self-test, and allowed/excluded claims;
contract errors go to standard error. The decision JSON includes `valid`, `status`, `exit_code`,
`validator_self_test`, `validator_detail`, `allowed_claims`, `excluded_claims` and `errors`.
`valid: true` can accompany exits `3` or `4`; it means the preflight is structurally valid, not ready.
A load-error object contains `valid`, `status`, `exit_code` and `errors` only.

### `validate`

`input` is a required operational-run envelope JSON path; `-` reads standard input. `--json` emits
a machine-readable validation result and, only when valid, its receipt. An envelope binds preflight,
acquisition, execution state and report. A bare report cannot establish a run.

```bash
python3 -B <skill-root>/scripts/dravux_run.py validate /path/to/run-envelope.json
python3 -B <skill-root>/scripts/dravux_run.py validate --json - < /path/to/run-envelope.json
```

| Exit | Meaning |
|---|---|
| `0` | Run contract valid; emits `DRAVUX RUN RECEIPT` or the JSON receipt. |
| `1` | Run contract invalid, including invalid preflight or hostile structures safely rejected during validation. |
| `2` | File/JSON loading failure, or command-line usage error. |

A valid run can record incomplete execution, automated `ERROR`, or final `INCOMPLETE`; exit `0`
proves the envelope is valid, not that the audit passed. Preflight stops inside an envelope are
validation failures here (exit `1`), not standalone-preflight exits `3` or `4`.
JSON includes `valid`, `exit_code` and `errors`, plus `receipt` only on success. Load errors also
include `status: LOAD_ERROR`. Text errors go to standard error; text receipts go to standard output.
Preflight diagnostics name the JSON path, what was expected and the found value's escaped
representation, cut to 80 characters. Text receipts escape controls and formatting; JSON preserves
the authoritative contract values.

### `output-dir`

Creates a `dravux-audits` directory outside protected Dravux trees. It is the only subcommand here
that creates directories; it neither writes an audit nor validates a report.

| Flag | Meaning |
|---|---|
| `--base BASE` | Starting folder; defaults to the current folder. Paths are expanded and resolved. |
| `--audit-id AUDIT_ID` | Optional per-audit subfolder: 1–64 lowercase ASCII letters, digits or hyphens. |
| `--strict` | Refuse instead of redirecting when the starting folder is inside a protected tree. |
| `--json` | Emit the full placement result instead of a message followed by the output path. |
| `-h`, `--help` | Show subcommand help and exit `0` without creating a directory. |

```bash
python3 -B <skill-root>/scripts/dravux_run.py output-dir --base /path/to/project --audit-id first-audit
python3 -B <skill-root>/scripts/dravux_run.py output-dir --strict --json
```

| Exit | Status | Meaning |
|---|---|---|
| `0` | `CREATED` or `REDIRECTED` | Output directory is ready; it may be an existing safe directory. |
| `2` | `INVALID` | Invalid audit name or starting-folder input; parser usage errors also exit `2`. |
| `5` | `REFUSED` | Protected-tree refusal, unsafe filesystem condition, unsupported POSIX directory-descriptor operations, or creation failure. |

Protected roots are detected by `SKILL.md` or `RELEASE_MANIFEST.json` markers of any type, including
directories and dangling symlinks. By default, a protected starting point redirects beside the
outermost protected root. Refusals fail closed. On text success the last line is the absolute output
path; failure diagnostics go to standard error. JSON fields are `command`, `status`, `exit_code`,
`base`, `guarded`, `guarded_root`, `output_dir`, `created` and `message`. JSON goes to standard output
even on refusal. Check the exit status and `created` before using `output_dir`.

## Interpretation and limits

Validation exits are separate from accessibility verdicts. Never turn a schema error into a target
failure, or an automated `PASS` into `VERIFIED PASS` while manual checks remain. If the bundled
validator cannot run, label the answer `UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

All validation stays offline. A hostname resolving to an internal IP can pass a literal URL check;
DNS resolution is permanently outside the validator. Acquisition tooling must enforce the separate
DNS/redirect policy in [SECURITY.md](../SECURITY.md). See [Quickstart](quickstart.md) for the full
workflow and [Troubleshooting](troubleshooting.md) for refusals.
