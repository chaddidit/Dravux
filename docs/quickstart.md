# Dravux Quickstart

## 1. Define and preflight the audit

Record the product surface, target, state, input type, requested evidence mode, included/excluded scope, required manual checks, and whether repair is authorized. Copy `plugins/dravux/skills/dravux/assets/preflight-template.json`, fill in only capabilities actually present, and run:

```bash
python3 plugins/dravux/skills/dravux/scripts/dravux_run.py preflight path/to/preflight.json
```

Continue only after `READY`. `LIMITATION_ACK_REQUIRED` means the user must explicitly accept the reduced mode. `UNSUPPORTED` means the current surface cannot establish a Dravux result.

## 2. Use the skill

Install or reference `plugins/dravux/skills/dravux/` in the location supported by your agent. Use the matching note under `adapters/`.

## 3. Create a report

Copy `plugins/dravux/skills/dravux/assets/report-template.json` to a working output directory. Do not put private local paths in public reports.

## 4. Validate the report

```bash
python3 scripts/validate_report.py path/to/report.json
```

For a response-only report, resolve the installed skill root and stream the complete JSON to its bundled validator instead of saving it in the project:

```bash
python3 <skill-root>/scripts/dravux_contract.py -
```

Do not present an in-chat or live-URL summary as a Dravux result until the validator exits `0`.

Exit codes:

- `0`: contract valid
- `1`: JSON loaded but violates the Dravux contract
- `2`: file or JSON loading error

## 5. Validate the operational run

For an audit, copy `plugins/dravux/skills/dravux/assets/run-envelope-template.json` and add the completed preflight, acquisition receipt, and report. Then run:

```bash
python3 plugins/dravux/skills/dravux/scripts/dravux_run.py validate path/to/run-envelope.json
```

Operational exit `0` emits the required run receipt. A bare report is not an established audit run. If either validator cannot execute, return `UNVALIDATED DRAFT — NOT A DRAVUX RESULT`.

## 6. Finish honestly

Place the run receipt first, then report findings, evidence, tests, errors, and manual checks remaining. Automated `PASS` plus pending manual checks is `INCOMPLETE`.
